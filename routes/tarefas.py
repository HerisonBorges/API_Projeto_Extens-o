from flask import Blueprint, jsonify, request

from database.conexao import conectar_banco


tarefas_bp = Blueprint("tarefas", __name__, url_prefix="/tarefas")

COLUNAS = "id, empresa_id, cliente_id, titulo, descricao, data_vencimento, concluida"


def montar_tarefa(t):
    return {
        "id": t[0],
        "empresa_id": t[1],
        "cliente_id": t[2],
        "titulo": t[3],
        "descricao": t[4],
        "data_vencimento": str(t[5]) if t[5] is not None else None,
        "concluida": t[6]
    }


@tarefas_bp.route("", methods=["GET"])
def listar_tarefas():
    empresa_id = request.args.get("empresa_id", type=int)
    concluida = request.args.get("concluida")

    if not empresa_id:
        return jsonify({
            "erro": "empresa_id é obrigatório."
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    if concluida is not None:
        filtro = concluida.lower() == "true"

        cursor.execute(f"""
            SELECT {COLUNAS}
            FROM tarefas
            WHERE empresa_id = %s AND concluida = %s
            ORDER BY data_vencimento, id;
        """, (empresa_id, filtro))
    else:
        cursor.execute(f"""
            SELECT {COLUNAS}
            FROM tarefas
            WHERE empresa_id = %s
            ORDER BY data_vencimento, id;
        """, (empresa_id,))

    resultados = cursor.fetchall()

    cursor.close()
    conexao.close()

    return jsonify([montar_tarefa(t) for t in resultados]), 200


@tarefas_bp.route("", methods=["POST"])
def criar_tarefa():
    dados = request.get_json()

    empresa_id = dados.get("empresa_id")
    cliente_id = dados.get("cliente_id")
    titulo = dados.get("titulo")
    descricao = dados.get("descricao")
    data_vencimento = dados.get("data_vencimento")

    if not empresa_id or not titulo:
        return jsonify({
            "erro": "empresa_id e titulo são obrigatórios."
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO tarefas (
            empresa_id,
            cliente_id,
            titulo,
            descricao,
            data_vencimento,
            concluida
        )
        VALUES (%s, %s, %s, %s, %s, FALSE)
        RETURNING id;
    """, (empresa_id, cliente_id, titulo, descricao, data_vencimento))

    tarefa_id = cursor.fetchone()[0]

    conexao.commit()

    cursor.close()
    conexao.close()

    return jsonify({
        "mensagem": "Tarefa criada com sucesso!",
        "tarefa_id": tarefa_id
    }), 201


@tarefas_bp.route("/<int:id>", methods=["PUT"])
def editar_tarefa(id):
    dados = request.get_json()

    cliente_id = dados.get("cliente_id")
    titulo = dados.get("titulo")
    descricao = dados.get("descricao")
    data_vencimento = dados.get("data_vencimento")

    if not titulo:
        return jsonify({
            "erro": "titulo é obrigatório."
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE tarefas
        SET cliente_id = %s,
            titulo = %s,
            descricao = %s,
            data_vencimento = %s
        WHERE id = %s;
    """, (cliente_id, titulo, descricao, data_vencimento, id))

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
def excluir_tarefa(id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        DELETE FROM tarefas
        WHERE id = %s;
    """, (id,))

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
def concluir_tarefa(id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE tarefas
        SET concluida = TRUE
        WHERE id = %s;
    """, (id,))

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
