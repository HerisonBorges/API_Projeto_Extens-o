import re

from flask import Blueprint, Response, g, jsonify, request

from database.conexao import get_db_connection
from pdf_faturamento import gerar_pdf_faturamento
from routes.interacoes import TIPOS_VALIDOS as CANAIS
from routes.oportunidades import ETAPA_FINAL, ETAPAS_VALIDAS
from seguranca import fuso_empresa, perfil_requerido, token_obrigatorio


relatorios_bp = Blueprint(
    "relatorios",
    __name__,
    url_prefix="/relatorios"
)

# Período -> unidade do date_trunc. "total" (ou ausente) = desde o início.
PERIODOS = {"total": None, "mes": "month", "trimestre": "quarter", "ano": "year"}


def calcular_relatorio(empresa_id, periodo):
    """KPIs comerciais (usado pelo JSON e pelo PDF: os mesmos números nos dois).

    ?periodo=mes|trimestre|ano|total (padrão total), no fuso da empresa:
      - vendas e receita: oportunidades fechadas dentro do período
      - taxa_conversao: das oportunidades criadas no período, % já fechadas
      - funil: retrato atual (não depende do período)
      - serie_mensal: receita fechada nos últimos 12 meses
      - canais: interações por tipo no período e clientes que compraram
    """
    p = {
        "empresa_id": empresa_id,
        "tz": fuso_empresa(),
        "unidade": PERIODOS[periodo],
        "final": ETAPA_FINAL,
    }

    with get_db_connection() as conexao, conexao.cursor() as cursor:
        cursor.execute("""
            SELECT CASE WHEN %(unidade)s::text IS NULL THEN NULL
                        ELSE date_trunc(%(unidade)s, NOW() AT TIME ZONE %(tz)s) AT TIME ZONE %(tz)s
                   END;
        """, p)
        p["inicio"] = cursor.fetchone()[0]
        p["inicio_local"] = None
        if p["inicio"] is not None:
            cursor.execute("SELECT to_char(%(inicio)s AT TIME ZONE %(tz)s, 'DD/MM/YYYY');", p)
            p["inicio_local"] = cursor.fetchone()[0]

        filtro_fechamento = "(%(inicio)s::timestamptz IS NULL OR o.etapa_atualizada_em >= %(inicio)s)"
        filtro_criacao = "(%(inicio)s::timestamptz IS NULL OR o.criado_em >= %(inicio)s)"

        cursor.execute(f"""
            SELECT COUNT(*), COALESCE(SUM(o.valor), 0)
            FROM oportunidades o
            WHERE o.empresa_id = %(empresa_id)s AND o.etapa = %(final)s
              AND {filtro_fechamento};
        """, p)
        vendas_fechadas, receita_total = cursor.fetchone()
        receita_total = float(receita_total)

        cursor.execute(f"""
            SELECT COUNT(*), COUNT(*) FILTER (WHERE o.etapa = %(final)s)
            FROM oportunidades o
            WHERE o.empresa_id = %(empresa_id)s AND {filtro_criacao};
        """, p)
        total_oportunidades, fechadas_da_coorte = cursor.fetchone()

        cursor.execute("""
            SELECT etapa, COUNT(*), COALESCE(SUM(valor), 0)
            FROM oportunidades
            WHERE empresa_id = %(empresa_id)s
            GROUP BY etapa;
        """, p)
        por_etapa = {linha[0]: (linha[1], float(linha[2])) for linha in cursor.fetchall()}

        cursor.execute(f"""
            SELECT o.id, o.titulo, o.valor, c.nome, o.etapa_atualizada_em,
                   to_char(o.etapa_atualizada_em AT TIME ZONE %(tz)s, 'DD/MM/YYYY')
            FROM oportunidades o
            LEFT JOIN clientes c ON c.id = o.cliente_id
            WHERE o.empresa_id = %(empresa_id)s AND o.etapa = %(final)s
              AND {filtro_fechamento}
            ORDER BY o.etapa_atualizada_em DESC, o.id DESC;
        """, p)
        vendas = [
            {
                "id": linha[0],
                "titulo": linha[1],
                "valor": float(linha[2]) if linha[2] is not None else 0,
                "cliente": linha[3],
                "fechado_em": linha[4].isoformat() if linha[4] else None,
                "fechado_em_local": linha[5]
            }
            for linha in cursor.fetchall()
        ]

        cursor.execute("""
            WITH meses AS (
                SELECT generate_series(
                    date_trunc('month', NOW() AT TIME ZONE %(tz)s) - INTERVAL '11 months',
                    date_trunc('month', NOW() AT TIME ZONE %(tz)s),
                    INTERVAL '1 month'
                ) AS mes
            )
            SELECT to_char(m.mes, 'YYYY-MM'), COALESCE(SUM(o.valor), 0), COUNT(o.id)
            FROM meses m
            LEFT JOIN oportunidades o
                   ON o.empresa_id = %(empresa_id)s
                  AND o.etapa = %(final)s
                  AND date_trunc('month', o.etapa_atualizada_em AT TIME ZONE %(tz)s) = m.mes
            GROUP BY m.mes
            ORDER BY m.mes;
        """, p)
        serie_mensal = [
            {"mes": linha[0], "receita": float(linha[1]), "vendas": linha[2]}
            for linha in cursor.fetchall()
        ]

        cursor.execute(f"""
            SELECT i.tipo,
                   COUNT(*),
                   COUNT(DISTINCT i.cliente_id),
                   COUNT(DISTINCT i.cliente_id) FILTER (WHERE EXISTS (
                       SELECT 1 FROM oportunidades o
                       WHERE o.cliente_id = i.cliente_id
                         AND o.empresa_id = %(empresa_id)s
                         AND o.etapa = %(final)s
                         AND {filtro_fechamento}
                   ))
            FROM interacoes i
            WHERE i.empresa_id = %(empresa_id)s
              AND (%(inicio)s::timestamptz IS NULL OR i.criado_em >= %(inicio)s)
            GROUP BY i.tipo;
        """, p)
        por_canal = {linha[0]: linha[1:] for linha in cursor.fetchall()}

    ticket_medio = receita_total / vendas_fechadas if vendas_fechadas else 0
    taxa_conversao = (
        fechadas_da_coorte / total_oportunidades * 100 if total_oportunidades else 0
    )

    funil = [
        {
            "etapa": etapa,
            "quantidade": por_etapa.get(etapa, (0, 0.0))[0],
            "valor_total": por_etapa.get(etapa, (0, 0.0))[1]
        }
        for etapa in ETAPAS_VALIDAS
    ]

    canais = [
        {
            "canal": canal,
            "interacoes": por_canal.get(canal, (0, 0, 0))[0],
            "clientes_contatados": por_canal.get(canal, (0, 0, 0))[1],
            "clientes_com_venda": por_canal.get(canal, (0, 0, 0))[2]
        }
        for canal in CANAIS
    ]

    return {
        "periodo": periodo,
        "inicio_periodo": p["inicio"].isoformat() if p["inicio"] else None,
        "inicio_periodo_local": p["inicio_local"],
        "vendas_fechadas": vendas_fechadas,
        "receita_total": receita_total,
        "ticket_medio": round(ticket_medio, 2),
        "taxa_conversao": round(taxa_conversao, 2),
        "total_oportunidades": total_oportunidades,
        "funil": funil,
        "serie_mensal": serie_mensal,
        "canais": canais,
        "vendas": vendas
    }


def _periodo_da_requisicao():
    periodo = request.args.get("periodo", "total")
    if periodo not in PERIODOS:
        return None, (jsonify({"erro": f"periodo inválido. Use um de: {list(PERIODOS)}"}), 400)
    return periodo, None


@relatorios_bp.route("/vendas", methods=["GET"])
@token_obrigatorio
@perfil_requerido("Gestor")
def relatorio_vendas():
    """?periodo=mes|trimestre|ano|total (padrão total). Ver calcular_relatorio."""
    periodo, erro = _periodo_da_requisicao()
    if erro:
        return erro
    return jsonify(calcular_relatorio(g.empresa_id, periodo)), 200


def _nome_arquivo(empresa, periodo, data):
    """'Loja Fênix' -> 'faturamento-loja-fenix-mes-2026-11-13.pdf' (só ASCII seguro)."""
    import unicodedata
    base = unicodedata.normalize("NFKD", empresa or "empresa").encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:40] or "empresa"
    return f"faturamento-{base}-{periodo}-{data}.pdf"


@relatorios_bp.route("/vendas/pdf", methods=["GET"])
@token_obrigatorio
@perfil_requerido("Gestor")
def relatorio_vendas_pdf():
    """Mesmos dados de /relatorios/vendas, em PDF com a marca SANDRO CRM."""
    periodo, erro = _periodo_da_requisicao()
    if erro:
        return erro

    relatorio = calcular_relatorio(g.empresa_id, periodo)

    with get_db_connection() as conexao, conexao.cursor() as cursor:
        cursor.execute("""
            SELECT e.nome, u.nome,
                   to_char(NOW() AT TIME ZONE %(tz)s, 'DD/MM/YYYY "às" HH24:MI'),
                   to_char(NOW() AT TIME ZONE %(tz)s, 'YYYY-MM-DD')
            FROM usuarios u JOIN empresas e ON e.id = u.empresa_id
            WHERE u.id = %(usuario_id)s AND u.empresa_id = %(empresa_id)s;
        """, {"tz": fuso_empresa(), "usuario_id": g.usuario_id, "empresa_id": g.empresa_id})
        empresa, usuario, gerado_em, data_arquivo = cursor.fetchone()

    fuso = fuso_empresa()
    rotulo_fuso = "horário de Brasília" if fuso == "America/Sao_Paulo" else fuso
    pdf = gerar_pdf_faturamento(relatorio, empresa, usuario, f"{gerado_em} ({rotulo_fuso})")

    return Response(pdf, mimetype="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{_nome_arquivo(empresa, periodo, data_arquivo)}"',
        # Dado financeiro: não guardar em cache de navegador nem de proxy
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    })
