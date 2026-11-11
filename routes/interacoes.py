from flask import Blueprint, g, jsonify, request

from database.conexao import get_db_connection
from seguranca import token_obrigatorio


interacoes_bp = Blueprint("interacoes", __name__, url_prefix="/interacoes")

TIPOS_VALIDOS = ["Ligação", "WhatsApp", "E-mail", "Reunião"]
LIMITE_PADRAO = 50
LIMITE_MAXIMO = 200
DESCRICAO_MAXIMA = 2000


def montar_interacao(i):
    return {
        "id": i[0],
        "cliente_id": i[1],
        "cliente_nome": i[2],
        "oportunidade_id": i[3],
        "usuario_id": i[4],
        "usuario_nome": i[5],
        "tipo": i[6],
        "descricao": i[7],
        "criado_em": i[8].isoformat()
    }


SELECT_INTERACOES = """
    SELECT i.id, i.cliente_id, c.nome, i.oportunidade_id, i.usuario_id, u.nome,
           i.tipo, i.descricao, i.criado_em
    FROM interacoes i
    JOIN clientes c ON c.id = i.cliente_id
    LEFT JOIN usuarios u ON u.id = i.usuario_id
"""


@interacoes_bp.route("", methods=["GET"])
@token_obrigatorio
def listar_interacoes():
    """Mais recentes primeiro. Filtros: cliente_id, limite (1-200)."""
    cliente_id = request.args.get("cliente_id", type=int)
    limite = request.args.get("limite", default=LIMITE_PADRAO, type=int)

    if not 1 <= limite <= LIMITE_MAXIMO:
        return jsonify({"erro": f"limite deve estar entre 1 e {LIMITE_MAXIMO}."}), 400

    with get_db_connection() as conexao, conexao.cursor() as cursor:
        cursor.execute(f"""
            {SELECT_INTERACOES}
            WHERE i.empresa_id = %(empresa_id)s
              AND (%(cliente_id)s::int IS NULL OR i.cliente_id = %(cliente_id)s::int)
            ORDER BY i.criado_em DESC, i.id DESC
            LIMIT %(limite)s;
        """, {"empresa_id": g.empresa_id, "cliente_id": cliente_id, "limite": limite})

        interacoes = [montar_interacao(i) for i in cursor.fetchall()]

    return jsonify(interacoes), 200


@interacoes_bp.route("", methods=["POST"])
@token_obrigatorio
def criar_interacao():
    dados = request.get_json(silent=True) or {}

    cliente_id = dados.get("cliente_id")
    oportunidade_id = dados.get("oportunidade_id")
    tipo = dados.get("tipo")
    descricao = dados.get("descricao")

    if not isinstance(cliente_id, int) or isinstance(cliente_id, bool):
        return jsonify({"erro": "cliente_id é obrigatório."}), 400

    if tipo not in TIPOS_VALIDOS:
        return jsonify({"erro": f"tipo inválido. Use um de: {TIPOS_VALIDOS}"}), 400

    if not isinstance(descricao, str) or not descricao.strip():
        return jsonify({"erro": "descricao é obrigatória."}), 400

    descricao = descricao.strip()

    if len(descricao) > DESCRICAO_MAXIMA:
        return jsonify({"erro": f"descricao aceita até {DESCRICAO_MAXIMA} caracteres."}), 400

    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT 1 FROM clientes WHERE id = %s AND empresa_id = %s;",
                           (cliente_id, g.empresa_id))
            if not cursor.fetchone():
                return jsonify({"erro": "Cliente não encontrado."}), 404

            if oportunidade_id is not None:
                # A oportunidade precisa ser da empresa E do mesmo cliente
                cursor.execute("""
                    SELECT 1 FROM oportunidades
                    WHERE id = %s AND empresa_id = %s AND cliente_id = %s;
                """, (oportunidade_id, g.empresa_id, cliente_id))
                if not cursor.fetchone():
                    return jsonify({"erro": "Oportunidade não encontrada para este cliente."}), 404

            cursor.execute("""
                INSERT INTO interacoes (empresa_id, cliente_id, oportunidade_id,
                                        usuario_id, tipo, descricao)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (g.empresa_id, cliente_id, oportunidade_id, g.usuario_id, tipo, descricao))
            interacao_id = cursor.fetchone()[0]

            cursor.execute(f"{SELECT_INTERACOES} WHERE i.id = %s;", (interacao_id,))
            interacao = montar_interacao(cursor.fetchone())

        conexao.commit()

    return jsonify({
        "mensagem": "Interação registrada com sucesso!",
        "interacao": interacao
    }), 201
