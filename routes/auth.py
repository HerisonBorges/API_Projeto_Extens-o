from flask import Blueprint, jsonify, request
import bcrypt

from database.conexao import conectar_banco
from seguranca import (
    SQL_DENTRO_JANELA,
    TZ_EMPRESA,
    formatar_hora,
    gerar_token,
    resposta_horario_bloqueado,
)


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["POST"])
def registrar():
    dados = request.get_json()

    nome_empresa = dados.get("nome_empresa")
    nome_usuario = dados.get("nome_usuario")
    email = dados.get("email")
    senha = dados.get("senha")

    if not nome_empresa or not nome_usuario or not email or not senha:
        return jsonify({
            "erro": "Todos os campos são obrigatórios."
        }), 400

    senha_hash = bcrypt.hashpw(
        senha.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO empresas (nome, email)
        VALUES (%s, %s)
        RETURNING id;
    """, (nome_empresa, email))

    empresa_id = cursor.fetchone()[0]

    cursor.execute("""
        INSERT INTO usuarios (empresa_id, nome, email, senha)
        VALUES (%s, %s, %s, %s)
        RETURNING id;
    """, (empresa_id, nome_usuario, email, senha_hash))

    usuario_id = cursor.fetchone()[0]

    conexao.commit()

    cursor.close()
    conexao.close()

    return jsonify({
        "mensagem": "Cadastro realizado com sucesso!",
        "empresa_id": empresa_id,
        "usuario_id": usuario_id
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    dados = request.get_json()

    email = dados.get("email")
    senha = dados.get("senha")

    if not email or not senha:
        return jsonify({
            "erro": "E-mail e senha são obrigatórios."
        }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(f"""
        SELECT id, empresa_id, nome, email, senha, perfil,
               hora_inicio_acesso, hora_fim_acesso,
               {SQL_DENTRO_JANELA}
        FROM usuarios
        WHERE email = %(email)s;
    """, {"email": email, "tz": TZ_EMPRESA})

    usuario = cursor.fetchone()

    cursor.close()
    conexao.close()

    if not usuario:
        return jsonify({
            "erro": "Usuário não encontrado."
        }), 404

    senha_correta = bcrypt.checkpw(
        senha.encode("utf-8"),
        usuario[4].encode("utf-8")
    )

    if not senha_correta:
        return jsonify({
            "erro": "Senha incorreta."
        }), 401

    # Janela checada só depois da senha: não revela horários a quem não autenticou
    if not usuario[8]:
        return resposta_horario_bloqueado(usuario[6], usuario[7])

    token = gerar_token(usuario[0], usuario[1], usuario[5])

    return jsonify({
        "mensagem": "Login realizado com sucesso!",
        "token": token,
        "usuario": {
            "id": usuario[0],
            "empresa_id": usuario[1],
            "nome": usuario[2],
            "email": usuario[3],
            "perfil": usuario[5],
            "hora_inicio_acesso": formatar_hora(usuario[6]),
            "hora_fim_acesso": formatar_hora(usuario[7])
        }
    }), 200


@auth_bp.route("/me/<int:id>", methods=["GET"])
def meus_dados(id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, empresa_id, nome, email
        FROM usuarios
        WHERE id = %s;
    """, (id,))

    usuario = cursor.fetchone()

    cursor.close()
    conexao.close()

    if not usuario:
        return jsonify({
            "erro": "Usuário não encontrado."
        }), 404

    return jsonify({
        "id": usuario[0],
        "empresa_id": usuario[1],
        "nome": usuario[2],
        "email": usuario[3]
    }), 200