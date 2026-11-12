import re

from flask import Blueprint, g, jsonify, request

from database.conexao import conectar_banco, get_db_connection
from iam import normalizar_email, validar_email
from seguranca import perfil_requerido, token_obrigatorio


clientes_bp = Blueprint("clientes", __name__, url_prefix="/clientes")

STATUS_VALIDOS = ("Lead", "Cliente", "Inativo")
_TELEFONE = re.compile(r"^[0-9()+\-.\s]{8,30}$")

SELECT_CLIENTES = """
    SELECT c.id, c.empresa_id, c.nome, c.email, c.telefone, c.status,
           c.atualizado_em, u.nome
    FROM clientes c
    LEFT JOIN usuarios u ON u.id = c.atualizado_por
"""


def montar_cliente(c):
    return {
        "id": c[0],
        "empresa_id": c[1],
        "nome": c[2],
        "email": c[3],
        "telefone": c[4],
        "status": c[5],
        "atualizado_em": c[6].isoformat() if c[6] else None,
        "atualizado_por_nome": c[7],
    }


def _vazio_para_none(valor):
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise ValueError
    valor = valor.strip()
    return valor or None


def validar_campos(dados, parcial):
    """Valida os campos presentes em `dados`.

    parcial=False (criação): nome obrigatório, status padrão Lead.
    parcial=True (alteração): só os campos enviados; os ausentes não mudam.
    Retorna (campos, erro). Enviar email/telefone vazio ou null apaga o valor.
    """
    campos = {}

    if "nome" in dados or not parcial:
        nome = dados.get("nome")
        if not isinstance(nome, str) or not nome.strip():
            return None, "nome é obrigatório."
        if len(nome.strip()) > 150:
            return None, "nome aceita até 150 caracteres."
        campos["nome"] = nome.strip()

    if "email" in dados:
        try:
            email = _vazio_para_none(dados["email"])
        except ValueError:
            return None, "email inválido."
        if email is not None:
            email = normalizar_email(email)
            if validar_email(email):
                return None, "email inválido."
        campos["email"] = email

    if "telefone" in dados:
        try:
            telefone = _vazio_para_none(dados["telefone"])
        except ValueError:
            return None, "telefone inválido."
        if telefone is not None and not _TELEFONE.match(telefone):
            return None, "telefone inválido. Use de 8 a 30 dígitos, com ( ) - + . ou espaços."
        campos["telefone"] = telefone

    if "status" in dados or not parcial:
        status = dados.get("status", "Lead")
        if status not in STATUS_VALIDOS:
            return None, f"status inválido. Use um de: {list(STATUS_VALIDOS)}"
        campos["status"] = status

    return campos, None


@clientes_bp.route("", methods=["GET"])
@token_obrigatorio
def listar_clientes():
    with get_db_connection() as conexao, conexao.cursor() as cursor:
        cursor.execute(f"{SELECT_CLIENTES} WHERE c.empresa_id = %s ORDER BY c.id;", (g.empresa_id,))
        return jsonify([montar_cliente(c) for c in cursor.fetchall()]), 200


@clientes_bp.route("", methods=["POST"])
@token_obrigatorio
def criar_cliente():
    campos, erro = validar_campos(request.get_json(silent=True) or {}, parcial=False)
    if erro:
        return jsonify({"erro": erro}), 400

    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute("""
                INSERT INTO clientes (empresa_id, nome, email, telefone, status)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (g.empresa_id, campos["nome"], campos.get("email"), campos.get("telefone"),
                  campos["status"]))
            cliente_id = cursor.fetchone()[0]
        conexao.commit()

    return jsonify({
        "mensagem": "Cliente cadastrado com sucesso!",
        "cliente_id": cliente_id
    }), 201


@clientes_bp.route("/<int:id>", methods=["GET"])
@token_obrigatorio
def buscar_cliente(id):
    with get_db_connection() as conexao, conexao.cursor() as cursor:
        cursor.execute(f"{SELECT_CLIENTES} WHERE c.id = %s AND c.empresa_id = %s;", (id, g.empresa_id))
        cliente = cursor.fetchone()

    if not cliente:
        return jsonify({"erro": "Cliente não encontrado."}), 404

    return jsonify(montar_cliente(cliente)), 200


@clientes_bp.route("/<int:id>", methods=["PUT"])
@token_obrigatorio
def editar_cliente(id):
    """Alteração parcial: só os campos enviados mudam (nome, email, telefone, status).

    Antes esta rota sobrescrevia todos os campos: enviar só o telefone
    apagava o e-mail e o status.
    """
    campos, erro = validar_campos(request.get_json(silent=True) or {}, parcial=True)
    if erro:
        return jsonify({"erro": erro}), 400
    if not campos:
        return jsonify({"erro": "Informe ao menos um campo: nome, email, telefone ou status."}), 400

    # Nomes de coluna vêm só da lista fixa de validar_campos (sem SQL dinâmico do usuário)
    atribuicoes = ", ".join(f"{coluna} = %({coluna})s" for coluna in campos)

    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(f"""
                UPDATE clientes
                SET {atribuicoes}, atualizado_em = NOW(), atualizado_por = %(usuario_id)s
                WHERE id = %(id)s AND empresa_id = %(empresa_id)s;
            """, {**campos, "usuario_id": g.usuario_id, "id": id, "empresa_id": g.empresa_id})

            if cursor.rowcount == 0:
                return jsonify({"erro": "Cliente não encontrado."}), 404

            cursor.execute(f"{SELECT_CLIENTES} WHERE c.id = %s;", (id,))
            cliente = cursor.fetchone()
        conexao.commit()

    return jsonify({
        "mensagem": "Cliente atualizado com sucesso!",
        "cliente": montar_cliente(cliente)
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
