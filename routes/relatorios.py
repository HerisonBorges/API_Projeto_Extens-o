from flask import Blueprint, jsonify, request

from database.conexao import conectar_banco


relatorios_bp = Blueprint(
    "relatorios",
    __name__,
    url_prefix="/relatorios"
)


@relatorios_bp.route("/vendas", methods=["GET"])
def relatorio_vendas():
    empresa_id = request.args.get("empresa_id", type=int)

    if not empresa_id:
        return jsonify({
            "erro": "empresa_id é obrigatório."
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    # Vendas fechadas: quantidade e receita
    cursor.execute("""
        SELECT COUNT(*), COALESCE(SUM(valor), 0)
        FROM oportunidades
        WHERE empresa_id = %s
        AND etapa = 'Fechado';
    """, (empresa_id,))

    vendas_fechadas, receita_total = cursor.fetchone()
    receita_total = float(receita_total)

    # Total de oportunidades (para taxa de conversão)
    cursor.execute("""
        SELECT COUNT(*)
        FROM oportunidades
        WHERE empresa_id = %s;
    """, (empresa_id,))

    total_oportunidades = cursor.fetchone()[0]

    # Quantidade e valor por etapa do funil
    cursor.execute("""
        SELECT etapa, COUNT(*), COALESCE(SUM(valor), 0)
        FROM oportunidades
        WHERE empresa_id = %s
        GROUP BY etapa
        ORDER BY etapa;
    """, (empresa_id,))

    funil = [
        {
            "etapa": linha[0],
            "quantidade": linha[1],
            "valor_total": float(linha[2])
        }
        for linha in cursor.fetchall()
    ]

    # Lista das vendas fechadas, com o nome do cliente
    cursor.execute("""
        SELECT o.id, o.titulo, o.valor, c.nome
        FROM oportunidades o
        LEFT JOIN clientes c ON c.id = o.cliente_id
        WHERE o.empresa_id = %s
        AND o.etapa = 'Fechado'
        ORDER BY o.id DESC;
    """, (empresa_id,))

    vendas = [
        {
            "id": linha[0],
            "titulo": linha[1],
            "valor": float(linha[2]) if linha[2] is not None else 0,
            "cliente": linha[3]
        }
        for linha in cursor.fetchall()
    ]

    cursor.close()
    conexao.close()

    ticket_medio = receita_total / vendas_fechadas if vendas_fechadas else 0
    taxa_conversao = (
        vendas_fechadas / total_oportunidades * 100
        if total_oportunidades else 0
    )

    return jsonify({
        "vendas_fechadas": vendas_fechadas,
        "receita_total": receita_total,
        "ticket_medio": round(ticket_medio, 2),
        "taxa_conversao": round(taxa_conversao, 2),
        "funil": funil,
        "vendas": vendas
    }), 200
