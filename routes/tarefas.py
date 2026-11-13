from flask import Blueprint, g, jsonify, request

from database.conexao import conectar_banco
from seguranca import fuso_empresa, perfil_requerido, token_obrigatorio


tarefas_bp = Blueprint("tarefas", __name__, url_prefix="/tarefas")

COLUNAS = (
    "id, empresa_id, cliente_id, titulo, descricao, "
    "data_vencimento, concluida, oportunidade_id"
)


def montar_tarefa(t):
    return {
        "id": t[0],
        "empresa_id": t[1],
        "cliente_id": t[2],
        "titulo": t[3],
        "descricao": t[4],
        "data_vencimento": str(t[5]) if t[5] is not None else None,
        "concluida": t[6],
        "oportunidade_id": t[7]
    }


def oportunidade_pertence_a_empresa(cursor, oportunidade_id, empresa_id):
    if oportunidade_id is None:
        return True

    cursor.execute("""
        SELECT 1 FROM oportunidades WHERE id = %s AND empresa_id = %s;
    """, (oportunidade_id, empresa_id))

    return cursor.fetchone() is not None


def validar_vinculos(cursor, cliente_id, oportunidade_id, empresa_id):
    """Retorna mensagem de erro ou None se os vínculos são da empresa."""
    if not cliente_pertence_a_empresa(cursor, cliente_id, empresa_id):
        return "Cliente não encontrado."

    if not oportunidade_pertence_a_empresa(cursor, oportunidade_id, empresa_id):
        return "Oportunidade não encontrada."

    return None


def cliente_pertence_a_empresa(cursor, cliente_id, empresa_id):
    if cliente_id is None:
        return True

    cursor.execute("""
        SELECT 1 FROM clientes WHERE id = %s AND empresa_id = %s;
    """, (cliente_id, empresa_id))

    return cursor.fetchone() is not None


@tarefas_bp.route("", methods=["GET"])
@token_obrigatorio
def listar_tarefas():
    concluida = request.args.get("concluida")

    conexao = conectar_banco()
    cursor = conexao.cursor()

    if concluida is not None:
        filtro = concluida.lower() == "true"

        cursor.execute(f"""
            SELECT {COLUNAS}
            FROM tarefas
            WHERE empresa_id = %s AND concluida = %s
            ORDER BY data_vencimento, id;
        """, (g.empresa_id, filtro))
    else:
        cursor.execute(f"""
            SELECT {COLUNAS}
            FROM tarefas
            WHERE empresa_id = %s
            ORDER BY data_vencimento, id;
        """, (g.empresa_id,))

    resultados = cursor.fetchall()

    cursor.close()
    conexao.close()

    return jsonify([montar_tarefa(t) for t in resultados]), 200


@tarefas_bp.route("/alertas", methods=["GET"])
@token_obrigatorio
def listar_alertas():
    """RF04: follow-ups vencidos e orçamentos parados há mais de X dias."""
    conexao = conectar_banco()
    cursor = conexao.cursor()

    # "Hoje" é o dia no fuso da empresa, não em UTC (o banco roda em UTC: entre
    # 21h e 24h em São Paulo o CURRENT_DATE já é amanhã)
    cursor.execute(f"""
        SELECT {COLUNAS}
        FROM tarefas
        WHERE empresa_id = %(empresa_id)s
          AND concluida = FALSE
          AND data_vencimento < (NOW() AT TIME ZONE %(tz)s)::date
        ORDER BY data_vencimento, id;
    """, {"empresa_id": g.empresa_id, "tz": fuso_empresa()})

    vencidas = [montar_tarefa(t) for t in cursor.fetchall()]

    cursor.execute("""
        SELECT COALESCE(
            (SELECT dias_alerta_orcamento FROM configuracoes WHERE empresa_id = %s),
            7
        );
    """, (g.empresa_id,))

    dias = cursor.fetchone()[0]

    cursor.execute("""
        SELECT id, titulo, cliente_id, valor,
               (NOW() AT TIME ZONE %(tz)s)::date
                 - (etapa_atualizada_em AT TIME ZONE %(tz)s)::date AS dias_parado
        FROM oportunidades
        WHERE empresa_id = %(empresa_id)s
          AND etapa = 'Proposta'
          AND etapa_atualizada_em < NOW() - make_interval(days => %(dias)s)
        ORDER BY etapa_atualizada_em;
    """, {"empresa_id": g.empresa_id, "dias": dias, "tz": fuso_empresa()})

    orcamentos_parados = [
        {
            "id": o[0],
            "titulo": o[1],
            "cliente_id": o[2],
            "valor": float(o[3]) if o[3] is not None else 0,
            "dias_parado": o[4]
        }
        for o in cursor.fetchall()
    ]

    cursor.close()
    conexao.close()

    return jsonify({
        "dias_alerta_orcamento": dias,
        "tarefas_vencidas": vencidas,
        "orcamentos_parados": orcamentos_parados
    }), 200


@tarefas_bp.route("", methods=["POST"])
@token_obrigatorio
def criar_tarefa():
    dados = request.get_json(silent=True) or {}

    cliente_id = dados.get("cliente_id")
    titulo = dados.get("titulo")
    descricao = dados.get("descricao")
    data_vencimento = dados.get("data_vencimento")
    oportunidade_id = dados.get("oportunidade_id")

    if not titulo:
        return jsonify({
            "erro": "titulo é obrigatório."
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    erro = validar_vinculos(cursor, cliente_id, oportunidade_id, g.empresa_id)

    if erro:
        cursor.close()
        conexao.close()
        return jsonify({"erro": erro}), 404

    cursor.execute("""
        INSERT INTO tarefas (
            empresa_id,
            cliente_id,
            oportunidade_id,
            titulo,
            descricao,
            data_vencimento,
            concluida
        )
        VALUES (%s, %s, %s, %s, %s, %s, FALSE)
        RETURNING id;
    """, (g.empresa_id, cliente_id, oportunidade_id, titulo, descricao,
          data_vencimento))

    tarefa_id = cursor.fetchone()[0]

    conexao.commit()

    cursor.close()
    conexao.close()

    return jsonify({
        "mensagem": "Tarefa criada com sucesso!",
        "tarefa_id": tarefa_id
    }), 201


@tarefas_bp.route("/<int:id>", methods=["PUT"])
@token_obrigatorio
def editar_tarefa(id):
    dados = request.get_json(silent=True) or {}

    cliente_id = dados.get("cliente_id")
    titulo = dados.get("titulo")
    descricao = dados.get("descricao")
    data_vencimento = dados.get("data_vencimento")
    oportunidade_id = dados.get("oportunidade_id")

    if not titulo:
        return jsonify({
            "erro": "titulo é obrigatório."
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    erro = validar_vinculos(cursor, cliente_id, oportunidade_id, g.empresa_id)

    if erro:
        cursor.close()
        conexao.close()
        return jsonify({"erro": erro}), 404

    cursor.execute("""
        UPDATE tarefas
        SET cliente_id = %s,
            oportunidade_id = %s,
            titulo = %s,
            descricao = %s,
            data_vencimento = %s
        WHERE id = %s AND empresa_id = %s;
    """, (cliente_id, oportunidade_id, titulo, descricao, data_vencimento,
          id, g.empresa_id))

    conexao.commit()

    linhas_alteradas = cursor.rowcount

    cursor.close()
    conexao.close()

    if linhas_alteradas == 0:
        return jsonify({
            "erro": "Tarefa não encontrada."
        }), 404

    return jsonify({
        "mensagem": "Tarefa atualizada com sucesso!"
    }), 200


@tarefas_bp.route("/<int:id>", methods=["DELETE"])
@token_obrigatorio
@perfil_requerido("Gestor")
def excluir_tarefa(id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        DELETE FROM tarefas
        WHERE id = %s AND empresa_id = %s;
    """, (id, g.empresa_id))

    conexao.commit()

    linhas_excluidas = cursor.rowcount

    cursor.close()
    conexao.close()

    if linhas_excluidas == 0:
        return jsonify({
            "erro": "Tarefa não encontrada."
        }), 404

    return jsonify({
        "mensagem": "Tarefa excluída com sucesso!"
    }), 200


@tarefas_bp.route("/<int:id>/concluir", methods=["PATCH"])
@token_obrigatorio
def concluir_tarefa(id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE tarefas
        SET concluida = TRUE
        WHERE id = %s AND empresa_id = %s;
    """, (id, g.empresa_id))

    conexao.commit()

    linhas_alteradas = cursor.rowcount

    cursor.close()
    conexao.close()

    if linhas_alteradas == 0:
        return jsonify({
            "erro": "Tarefa não encontrada."
        }), 404

    return jsonify({
        "mensagem": "Tarefa concluída com sucesso!"
    }), 200
