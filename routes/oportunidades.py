from datetime import datetime

from flask import Blueprint, g, jsonify, request

from database.conexao import conectar_banco
from seguranca import TZ_EMPRESA, perfil_requerido, token_obrigatorio


oportunidades_bp = Blueprint(
    "oportunidades",
    __name__,
    url_prefix="/oportunidades"
)


ETAPAS_VALIDAS = [
    "Prospecção",
    "Qualificação",
    "Proposta",
    "Negociação",
    "Fechado"
]

ETAPA_INICIAL = ETAPAS_VALIDAS[0]
ETAPA_FINAL = ETAPAS_VALIDAS[-1]

DIAS_RECICLAGEM_MAX = 365

COLUNAS = (
    "o.id, o.empresa_id, o.cliente_id, o.titulo, o.valor, o.etapa, "
    "o.data_reciclagem_agendada, o.status_reciclagem, o.oportunidade_origem_id, "
    "o.responsavel_id, u.nome, o.criado_em, o.etapa_atualizada_em"
)

# Responsável é opcional (usuário pode ter sido removido): LEFT JOIN
FROM_OPORTUNIDADES = """
    FROM oportunidades o
    LEFT JOIN usuarios u ON u.id = o.responsavel_id
"""

# Ao sair da etapa final, um agendamento pendente perde o sentido
SQL_CANCELA_RECICLAGEM = """
    status_reciclagem = CASE
        WHEN status_reciclagem = 'pendente' AND %(etapa)s <> %(etapa_final)s
        THEN 'cancelado'
        ELSE status_reciclagem
    END
"""


def montar_oportunidade(o):
    return {
        "id": o[0],
        "empresa_id": o[1],
        "cliente_id": o[2],
        "titulo": o[3],
        "valor": float(o[4]) if o[4] is not None else 0,
        "etapa": o[5],
        "data_reciclagem_agendada": o[6].isoformat() if o[6] else None,
        "status_reciclagem": o[7],
        "oportunidade_origem_id": o[8],
        "responsavel_id": o[9],
        "responsavel_nome": o[10],
        "criado_em": o[11].isoformat() if o[11] else None,
        "etapa_atualizada_em": o[12].isoformat() if o[12] else None
    }


def cliente_pertence_a_empresa(cursor, cliente_id, empresa_id):
    if cliente_id is None:
        return True

    cursor.execute("""
        SELECT 1 FROM clientes WHERE id = %s AND empresa_id = %s;
    """, (cliente_id, empresa_id))

    return cursor.fetchone() is not None


@oportunidades_bp.route("", methods=["GET"])
@token_obrigatorio
def listar_oportunidades():
    etapa = request.args.get("etapa")

    conexao = conectar_banco()
    cursor = conexao.cursor()

    if etapa:
        cursor.execute(f"""
            SELECT {COLUNAS}
            {FROM_OPORTUNIDADES}
            WHERE o.empresa_id = %s AND o.etapa = %s
            ORDER BY o.id;
        """, (g.empresa_id, etapa))
    else:
        cursor.execute(f"""
            SELECT {COLUNAS}
            {FROM_OPORTUNIDADES}
            WHERE o.empresa_id = %s
            ORDER BY o.id;
        """, (g.empresa_id,))

    resultados = cursor.fetchall()

    cursor.close()
    conexao.close()

    return jsonify([montar_oportunidade(o) for o in resultados]), 200


@oportunidades_bp.route("/<int:id>", methods=["GET"])
@token_obrigatorio
def buscar_oportunidade(id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(f"""
        SELECT {COLUNAS}
        {FROM_OPORTUNIDADES}
        WHERE o.id = %s AND o.empresa_id = %s;
    """, (id, g.empresa_id))

    oportunidade = cursor.fetchone()

    cursor.close()
    conexao.close()

    if not oportunidade:
        return jsonify({
            "erro": "Oportunidade não encontrada."
        }), 404

    return jsonify(montar_oportunidade(oportunidade)), 200


@oportunidades_bp.route("", methods=["POST"])
@token_obrigatorio
def criar_oportunidade():
    dados = request.get_json(silent=True) or {}

    cliente_id = dados.get("cliente_id")
    titulo = dados.get("titulo")
    valor = dados.get("valor", 0)
    etapa = dados.get("etapa", ETAPAS_VALIDAS[0])

    if not titulo:
        return jsonify({
            "erro": "titulo é obrigatório."
        }), 400

    if etapa not in ETAPAS_VALIDAS:
        return jsonify({
            "erro": f"Etapa inválida. Use uma de: {ETAPAS_VALIDAS}"
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    if not cliente_pertence_a_empresa(cursor, cliente_id, g.empresa_id):
        cursor.close()
        conexao.close()
        return jsonify({
            "erro": "Cliente não encontrado."
        }), 404

    cursor.execute("""
        INSERT INTO oportunidades (empresa_id, cliente_id, titulo, valor, etapa,
                                   responsavel_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
    """, (g.empresa_id, cliente_id, titulo, valor, etapa, g.usuario_id))

    oportunidade_id = cursor.fetchone()[0]

    conexao.commit()

    cursor.close()
    conexao.close()

    return jsonify({
        "mensagem": "Oportunidade criada com sucesso!",
        "oportunidade_id": oportunidade_id
    }), 201


@oportunidades_bp.route("/<int:id>", methods=["PUT"])
@token_obrigatorio
def editar_oportunidade(id):
    dados = request.get_json(silent=True) or {}

    cliente_id = dados.get("cliente_id")
    titulo = dados.get("titulo")
    valor = dados.get("valor", 0)
    etapa = dados.get("etapa")

    if not titulo or not etapa:
        return jsonify({
            "erro": "titulo e etapa são obrigatórios."
        }), 400

    if etapa not in ETAPAS_VALIDAS:
        return jsonify({
            "erro": f"Etapa inválida. Use uma de: {ETAPAS_VALIDAS}"
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    if not cliente_pertence_a_empresa(cursor, cliente_id, g.empresa_id):
        cursor.close()
        conexao.close()
        return jsonify({
            "erro": "Cliente não encontrado."
        }), 404

    cursor.execute(f"""
        UPDATE oportunidades
        SET cliente_id = %(cliente_id)s,
            titulo = %(titulo)s,
            valor = %(valor)s,
            etapa = %(etapa)s,
            etapa_atualizada_em = CASE WHEN etapa <> %(etapa)s THEN NOW()
                                       ELSE etapa_atualizada_em END,
            {SQL_CANCELA_RECICLAGEM}
        WHERE id = %(id)s AND empresa_id = %(empresa_id)s;
    """, {
        "cliente_id": cliente_id,
        "titulo": titulo,
        "valor": valor,
        "etapa": etapa,
        "etapa_final": ETAPA_FINAL,
        "id": id,
        "empresa_id": g.empresa_id
    })

    conexao.commit()

    linhas_alteradas = cursor.rowcount

    cursor.close()
    conexao.close()

    if linhas_alteradas == 0:
        return jsonify({
            "erro": "Oportunidade não encontrada."
        }), 404

    return jsonify({
        "mensagem": "Oportunidade atualizada com sucesso!"
    }), 200


@oportunidades_bp.route("/<int:id>", methods=["DELETE"])
@token_obrigatorio
@perfil_requerido("Gestor")
def excluir_oportunidade(id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        DELETE FROM oportunidades
        WHERE id = %s AND empresa_id = %s;
    """, (id, g.empresa_id))

    conexao.commit()

    linhas_excluidas = cursor.rowcount

    cursor.close()
    conexao.close()

    if linhas_excluidas == 0:
        return jsonify({
            "erro": "Oportunidade não encontrada."
        }), 404

    return jsonify({
        "mensagem": "Oportunidade excluída com sucesso!"
    }), 200


@oportunidades_bp.route("/<int:id>/etapa", methods=["PATCH"])
@token_obrigatorio
def mover_oportunidade(id):
    dados = request.get_json(silent=True) or {}

    etapa = dados.get("etapa")

    if not etapa:
        return jsonify({
            "erro": "etapa é obrigatória."
        }), 400

    if etapa not in ETAPAS_VALIDAS:
        return jsonify({
            "erro": f"Etapa inválida. Use uma de: {ETAPAS_VALIDAS}"
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(f"""
        UPDATE oportunidades
        SET etapa = %(etapa)s,
            etapa_atualizada_em = NOW(),
            {SQL_CANCELA_RECICLAGEM}
        WHERE id = %(id)s AND empresa_id = %(empresa_id)s;
    """, {
        "etapa": etapa,
        "etapa_final": ETAPA_FINAL,
        "id": id,
        "empresa_id": g.empresa_id
    })

    conexao.commit()

    linhas_alteradas = cursor.rowcount

    cursor.close()
    conexao.close()

    if linhas_alteradas == 0:
        return jsonify({
            "erro": "Oportunidade não encontrada."
        }), 404

    return jsonify({
        "mensagem": "Oportunidade movida com sucesso!",
        "etapa": etapa
    }), 200


# ---------------------------------------------------------------------------
# Reciclagem pós-venda
# ---------------------------------------------------------------------------

def interpretar_agendamento(dados):
    """Converte o body em uma expressão SQL de timestamptz.

    Retorna (expressao_sql, parametros) ou (None, mensagem_de_erro).
    Modos aceitos (exatamente um):
      - "dias": inteiro de 1 a 365 -> NOW() + X dias
      - "data_agendada": ISO 8601
          * "2026-12-25"            -> meia-noite no fuso da empresa
          * "2026-12-25T09:00:00"   -> horário no fuso da empresa
          * "2026-12-25T00:00:00Z"  -> instante exato (com fuso)
    """
    tem_data = dados.get("data_agendada") is not None
    tem_dias = dados.get("dias") is not None

    if tem_data == tem_dias:
        return None, "Informe apenas um: data_agendada (ISO 8601) ou dias (inteiro)."

    if tem_dias:
        dias = dados["dias"]

        if (not isinstance(dias, int) or isinstance(dias, bool)
                or not 1 <= dias <= DIAS_RECICLAGEM_MAX):
            return None, f"dias deve ser um inteiro entre 1 e {DIAS_RECICLAGEM_MAX}."

        return "NOW() + make_interval(days => %(valor)s)", {"valor": dias}

    texto = dados["data_agendada"]

    if not isinstance(texto, str):
        return None, "data_agendada deve ser um texto ISO 8601."

    if len(texto) == 10:
        try:
            datetime.strptime(texto, "%Y-%m-%d")
        except ValueError:
            return None, "data_agendada inválida. Use AAAA-MM-DD."

        return "(%(valor)s::date)::timestamp AT TIME ZONE %(tz)s", {"valor": texto}

    normalizado = texto.replace("Z", "+00:00")

    try:
        instante = datetime.fromisoformat(normalizado)
    except ValueError:
        return None, "data_agendada inválida. Use ISO 8601, ex.: 2026-12-25T00:00:00Z."

    if instante.tzinfo is not None:
        return "%(valor)s::timestamptz", {"valor": normalizado}

    return "%(valor)s::timestamp AT TIME ZONE %(tz)s", {"valor": normalizado}


@oportunidades_bp.route("/<int:id>/agendar-reciclagem", methods=["POST"])
@token_obrigatorio
def agendar_reciclagem(id):
    dados = request.get_json(silent=True) or {}

    expressao, extra = interpretar_agendamento(dados)

    if expressao is None:
        return jsonify({"erro": extra}), 400

    parametros = {
        **extra,
        "tz": TZ_EMPRESA,
        "id": id,
        "empresa_id": g.empresa_id
    }

    conexao = conectar_banco()
    cursor = conexao.cursor()

    # FOR UPDATE: evita corrida com o worker ou com outra edição simultânea
    cursor.execute(f"""
        SELECT etapa, {expressao}, ({expressao}) > NOW()
        FROM oportunidades
        WHERE id = %(id)s AND empresa_id = %(empresa_id)s
        FOR UPDATE;
    """, parametros)

    linha = cursor.fetchone()

    if not linha:
        conexao.rollback()
        cursor.close()
        conexao.close()
        return jsonify({"erro": "Oportunidade não encontrada."}), 404

    etapa, data_agendada, futura = linha

    if etapa != ETAPA_FINAL:
        conexao.rollback()
        cursor.close()
        conexao.close()
        return jsonify({
            "erro": f"Só oportunidades na etapa '{ETAPA_FINAL}' podem ser recicladas."
        }), 409

    if not futura:
        conexao.rollback()
        cursor.close()
        conexao.close()
        return jsonify({
            "erro": "A data da reciclagem precisa estar no futuro."
        }), 400

    cursor.execute("""
        UPDATE oportunidades
        SET data_reciclagem_agendada = %(data)s,
            status_reciclagem = 'pendente'
        WHERE id = %(id)s AND empresa_id = %(empresa_id)s;
    """, {"data": data_agendada, "id": id, "empresa_id": g.empresa_id})

    conexao.commit()

    cursor.close()
    conexao.close()

    return jsonify({
        "mensagem": "Reciclagem agendada com sucesso!",
        "oportunidade_id": id,
        "data_reciclagem_agendada": data_agendada.isoformat(),
        "status_reciclagem": "pendente"
    }), 200


@oportunidades_bp.route("/<int:id>/agendar-reciclagem", methods=["DELETE"])
@token_obrigatorio
def cancelar_reciclagem(id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE oportunidades
        SET status_reciclagem = 'cancelado'
        WHERE id = %s AND empresa_id = %s AND status_reciclagem = 'pendente'
        RETURNING id;
    """, (id, g.empresa_id))

    cancelada = cursor.fetchone()

    if not cancelada:
        cursor.execute("""
            SELECT 1 FROM oportunidades WHERE id = %s AND empresa_id = %s;
        """, (id, g.empresa_id))
        existe = cursor.fetchone()

        conexao.rollback()
        cursor.close()
        conexao.close()

        if not existe:
            return jsonify({"erro": "Oportunidade não encontrada."}), 404

        return jsonify({"erro": "Não há reciclagem pendente para cancelar."}), 409

    conexao.commit()

    cursor.close()
    conexao.close()

    return jsonify({
        "mensagem": "Reciclagem cancelada.",
        "status_reciclagem": "cancelado"
    }), 200
