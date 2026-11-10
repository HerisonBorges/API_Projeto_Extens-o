from flask import Blueprint, g, jsonify, request

from database.conexao import conectar_banco
from seguranca import perfil_requerido, token_obrigatorio


clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")

COLUNAS = "id, empresa_id, nome, email, telefone, status"


def montar_cliente(c):
    return {
        "id": c[0],
        "empresa_id": c[1],
        "nome": c[2],
        "email": c[3],
        "telefone": c[4],
        "status": c[5]
    }


@clientes_bp.route("", methods=["GET"])
@token_obrigatorio
def listar_clientes():
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(f"""
        SELECT {COLUNAS}
        FROM clientes
        WHERE empresa_id = %s
        ORDER BY id;
    """, (g.empresa_id,))

    resultados = cursor.fetchall()

    cursor.close()
    conexao.close()

    return jsonify([montar_cliente(c) for c in resultados]), 200


@clientes_bp.route("", methods=["POST"])
@token_obrigatorio
def criar_cliente():
    dados = request.get_json(silent=True) or {}

    nome = dados.get("nome")
    email = dados.get("email")
    telefone = dados.get("telefone")
    status = dados.get("status", "Lead")

    if not nome:
        return jsonify({
            "erro": "nome é obrigatório."
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO clientes (empresa_id, nome, email, telefone, status)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, (g.empresa_id, nome, email, telefone, status))

    cliente_id = cursor.fetchone()[0]

    conexao.commit()

    cursor.close()
    conexao.close()

    return jsonify({
        "mensagem": "Cliente cadastrado com sucesso!",
        "cliente_id": cliente_id
    }), 201


@clientes_bp.route("/<int:id>", methods=["GET"])
@token_obrigatorio
def buscar_cliente(id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(f"""
        SELECT {COLUNAS}
        FROM clientes
        WHERE id = %s AND empresa_id = %s;
    """, (id, g.empresa_id))

    cliente = cursor.fetchone()

    cursor.close()
    conexao.close()

    if not cliente:
        return jsonify({
            "erro": "Cliente não encontrado."
        }), 404

    return jsonify(montar_cliente(cliente)), 200


@clientes_bp.route("/<int:id>", methods=["PUT"])
@token_obrigatorio
def editar_cliente(id):
    dados = request.get_json(silent=True) or {}

    nome = dados.get("nome")
    email = dados.get("email")
    telefone = dados.get("telefone")
    status = dados.get("status")

    if not nome:
        return jsonify({
            "erro": "nome é obrigatório."
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE clientes
        SET nome = %s,
            email = %s,
            telefone = %s,
            status = %s
        WHERE id = %s AND empresa_id = %s;
    """, (nome, email, telefone, status, id, g.empresa_id))

    conexao.commit()

    linhas_alteradas = cursor.rowcount

    cursor.close()
    conexao.close()

    if linhas_alteradas == 0:
        return jsonify({
            "erro": "Cliente não encontrado."
        }), 404

    return jsonify({
        "mensagem": "Cliente atualizado com sucesso!"
    }), 200


@clientes_bp.route("/<int:id>", methods=["DELETE"])
@token_obrigatorio
@perfil_requerido("Gestor")
def excluir_cliente(id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        DELETE FROM clientes
        WHERE id = %s AND empresa_id = %s;
    """, (id, g.empresa_id))

    conexao.commit()

    linhas_excluidas = cursor.rowcount

    cursor.close()
    conexao.close()

    if linhas_excluidas == 0:
        return jsonify({
            "erro": "Cliente não encontrado."
        }), 404

    return jsonify({
        "mensagem": "Cliente excluído com sucesso!"
    }), 200
