from flask import Blueprint, jsonify, request

from database.conexao import conectar_banco


clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")

@clientes_bp.route("", methods=["GET"])
def listar_clientes():
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, empresa_id, nome, email, telefone, status
        FROM clientes
        ORDER BY id;
    """)

    resultados = cursor.fetchall()

    cursor.close()
    conexao.close()

    clientes = []

    for cliente in resultados:
        clientes.append({
            "id": cliente[0],
            "empresa_id": cliente[1],
            "nome": cliente[2],
            "email": cliente[3],
            "telefone": cliente[4],
            "status": cliente[5]
        })

    return jsonify(clientes), 200

@clientes_bp.route("", methods=["POST"])
def criar_cliente():
    dados = request.get_json()

    empresa_id = dados.get("empresa_id")
    nome = dados.get("nome")
    email = dados.get("email")
    telefone = dados.get("telefone")
    status = dados.get("status", "Lead")

    if not empresa_id or not nome:
        return jsonify({
            "erro": "empresa_id e nome são obrigatórios."
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO clientes (empresa_id, nome, email, telefone, status)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, (empresa_id, nome, email, telefone, status))

    cliente_id = cursor.fetchone()[0]

    conexao.commit()

    cursor.close()
    conexao.close()

    return jsonify({
        "mensagem": "Cliente cadastrado com sucesso!",
        "cliente_id": cliente_id
    }), 201

@clientes_bp.route("/<int:id>", methods=["GET"])
def buscar_cliente(id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, empresa_id, nome, email, telefone, status
        FROM clientes
        WHERE id = %s;
    """, (id,))

    cliente = cursor.fetchone()

    cursor.close()
    conexao.close()

    if not cliente:
        return jsonify({
            "erro": "Cliente não encontrado."
        }), 404

    return jsonify({
        "id": cliente[0],
        "empresa_id": cliente[1],
        "nome": cliente[2],
        "email": cliente[3],
        "telefone": cliente[4],
        "status": cliente[5]
    }), 200

@clientes_bp.route("/<int:id>", methods=["PUT"])
def editar_cliente(id):
    dados = request.get_json()

    nome = dados.get("nome")
    email = dados.get("email")
    telefone = dados.get("telefone")
    status = dados.get("status")

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        UPDATE clientes
        SET nome = %s,
            email = %s,
            telefone = %s,
            status = %s
        WHERE id = %s;
    """, (nome, email, telefone, status, id))

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
def excluir_cliente(id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        DELETE FROM clientes
        WHERE id = %s;
    """, (id,))

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