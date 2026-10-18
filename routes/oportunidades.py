from flask import Blueprint, jsonify, request

from database.conexao import conectar_banco


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

COLUNAS = "id, empresa_id, cliente_id, titulo, valor, etapa"


def montar_oportunidade(o):
    return {
        "id": o[0],
        "empresa_id": o[1],
        "cliente_id": o[2],
        "titulo": o[3],
        "valor": float(o[4]) if o[4] is not None else 0,
        "etapa": o[5]
    }


@oportunidades_bp.route("", methods=["GET"])
def listar_oportunidades():
    empresa_id = request.args.get("empresa_id", type=int)
    etapa = request.args.get("etapa")

    if not empresa_id:
        return jsonify({
            "erro": "empresa_id é obrigatório."
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    if etapa:
        cursor.execute(f"""
            SELECT {COLUNAS}
            FROM oportunidades
            WHERE empresa_id = %s AND etapa = %s
            ORDER BY id;
        """, (empresa_id, etapa))
    else:
        cursor.execute(f"""
            SELECT {COLUNAS}
            FROM oportunidades
            WHERE empresa_id = %s
            ORDER BY id;
        """, (empresa_id,))

    resultados = cursor.fetchall()

    cursor.close()
    conexao.close()

    return jsonify([montar_oportunidade(o) for o in resultados]), 200


@oportunidades_bp.route("/<int:id>", methods=["GET"])
def buscar_oportunidade(id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(f"""
        SELECT {COLUNAS}
        FROM oportunidades
        WHERE id = %s;
    """, (id,))

    oportunidade = cursor.fetchone()

    cursor.close()
    conexao.close()

    if not oportunidade:
        return jsonify({
            "erro": "Oportunidade não encontrada."
        }), 404

    return jsonify(montar_oportunidade(oportunidade)), 200


@oportunidades_bp.route("", methods=["POST"])
def criar_oportunidade():
    dados = request.get_json()

    empresa_id = dados.get("empresa_id")
    cliente_id = dados.get("cliente_id")
    titulo = dados.get("titulo")
    valor = dados.get("valor", 0)
    etapa = dados.get("etapa", ETAPAS_VALIDAS[0])

    if not empresa_id or not titulo:
        return jsonify({
            "erro": "empresa_id e titulo são obrigatórios."
        }), 400

    if etapa not in ETAPAS_VALIDAS:
        return jsonify({
            "erro": f"Etapa inválida. Use uma de: {ETAPAS_VALIDAS}"
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO oportunidades (empresa_id, cliente_id, titulo, valor, etapa)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, (empresa_id, cliente_id, titulo, valor, etapa))

    oportunidade_id = cursor.fetchone()[0]

    conexao.commit()

    cursor.close()
    conexao.close()

    return jsonify({
        "mensagem": "Oportunidade criada com sucesso!",
        "oportunidade_id": oportunidade_id
    }), 201


@oportunidades_bp.route("/<int:id>", methods=["PUT"])
def editar_oportunidade(id):
    dados = request.get_json()

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

    cursor.execute("""
        UPDATE oportunidades
        SET cliente_id = %s,
            titulo = %s,
            valor = %s,
            etapa = %s
        WHERE id = %s;
    """, (cliente_id, titulo, valor, etapa, id))

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
def excluir_oportunidade(id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        DELETE FROM oportunidades
        WHERE id = %s;
    """, (id,))

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
def mover_oportunidade(id):
    dados = request.get_json()

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

    cursor.execute("""
        UPDATE oportunidades
        SET etapa = %s
        WHERE id = %s;
    """, (etapa, id))

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
