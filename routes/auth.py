from flask import Blueprint, g, jsonify, request
from psycopg2 import errors

from database.conexao import get_db_connection
from iam import (
    MINUTOS_DE_BLOQUEIO,
    TENTATIVAS_ANTES_DO_BLOQUEIO,
    auditar,
    gerar_hash,
    normalizar_email,
    senha_confere,
    validar_email,
    validar_nome,
    validar_senha,
)
from seguranca import (
    SQL_DENTRO_JANELA,
    TZ_EMPRESA,
    formatar_hora,
    gerar_token,
    permitir_com_senha_pendente,
    resposta_horario_bloqueado,
    token_obrigatorio,
)


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Mesma resposta para e-mail inexistente e senha errada: não revela quem tem conta
CREDENCIAIS_INVALIDAS = ({"erro": "E-mail ou senha inválidos."}, 401)


def montar_usuario(u):
    return {
        "id": u["id"],
        "empresa_id": u["empresa_id"],
        "empresa_nome": u["empresa_nome"],
        "nome": u["nome"],
        "email": u["email"],
        "perfil": u["perfil"],
        "hora_inicio_acesso": formatar_hora(u["hora_inicio_acesso"]),
        "hora_fim_acesso": formatar_hora(u["hora_fim_acesso"]),
        "deve_trocar_senha": u["deve_trocar_senha"],
    }


SELECT_USUARIO = f"""
    SELECT u.id, u.empresa_id, e.nome AS empresa_nome, u.nome, u.email, u.senha,
           u.perfil, u.hora_inicio_acesso, u.hora_fim_acesso,
           {SQL_DENTRO_JANELA.replace("hora_", "u.hora_")} AS dentro_janela,
           u.ativo, u.deve_trocar_senha, u.token_versao,
           (u.bloqueado_ate IS NOT NULL AND u.bloqueado_ate > NOW()) AS bloqueado,
           CEIL(EXTRACT(EPOCH FROM (u.bloqueado_ate - NOW())) / 60) AS minutos_bloqueio,
           (u.deve_trocar_senha AND u.senha_temporaria_expira_em < NOW()) AS temporaria_expirada
    FROM usuarios u
    JOIN empresas e ON e.id = u.empresa_id
"""


def buscar_usuario(cursor, where, params):
    cursor.execute(f"{SELECT_USUARIO} WHERE {where};", {**params, "tz": TZ_EMPRESA})
    linha = cursor.fetchone()
    if not linha:
        return None
    return dict(zip([c.name for c in cursor.description], linha))


@auth_bp.route("/register", methods=["POST"])
def registrar():
    """Cria uma empresa nova e o seu primeiro Gestor."""
    dados = request.get_json(silent=True) or {}

    nome_empresa = (dados.get("nome_empresa") or "").strip()
    nome_usuario = dados.get("nome_usuario")
    email = normalizar_email(dados.get("email"))
    senha = dados.get("senha")

    if not nome_empresa or len(nome_empresa) > 150:
        return jsonify({"erro": "Nome da empresa é obrigatório (até 150 caracteres)."}), 400

    problema = validar_nome(nome_usuario) or validar_email(email) or validar_senha(senha, email)
    if problema:
        return jsonify({"erro": problema}), 400

    with get_db_connection() as conexao:
        try:
            with conexao.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO empresas (nome, email) VALUES (%s, %s) RETURNING id;
                """, (nome_empresa, email))
                empresa_id = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO usuarios (empresa_id, nome, email, senha, perfil, senha_alterada_em)
                    VALUES (%s, %s, %s, %s, 'Gestor', NOW())
                    RETURNING id;
                """, (empresa_id, nome_usuario.strip(), email, gerar_hash(senha)))
                usuario_id = cursor.fetchone()[0]

                auditar(cursor, empresa_id, "usuario_criado", ator_id=usuario_id, alvo_id=usuario_id,
                        detalhes={"perfil": "Gestor", "origem": "cadastro_da_empresa"})
            conexao.commit()
        except errors.UniqueViolation:
            conexao.rollback()
            return jsonify({"erro": "Este e-mail já está em uso."}), 409

    return jsonify({
        "mensagem": "Cadastro realizado com sucesso!",
        "empresa_id": empresa_id,
        "usuario_id": usuario_id
    }), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    dados = request.get_json(silent=True) or {}

    email = normalizar_email(dados.get("email"))
    senha = dados.get("senha")

    if not email or not isinstance(senha, str) or not senha:
        return jsonify({"erro": "E-mail e senha são obrigatórios."}), 400

    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            usuario = buscar_usuario(cursor, "lower(u.email) = %(email)s", {"email": email})

            if not usuario:
                senha_confere(senha, None)  # mesmo custo de tempo de uma conta real
                return jsonify(CREDENCIAIS_INVALIDAS[0]), CREDENCIAIS_INVALIDAS[1]

            if usuario["bloqueado"]:
                minutos = int(usuario["minutos_bloqueio"] or 1)
                return jsonify({
                    "error": "LOGIN_BLOQUEADO",
                    "erro": f"Muitas tentativas sem sucesso. Tente de novo em {minutos} min "
                            "ou peça ao gestor para redefinir sua senha."
                }), 429

            if not senha_confere(senha, usuario["senha"]):
                cursor.execute("""
                    UPDATE usuarios SET tentativas_falhas = tentativas_falhas + 1
                    WHERE id = %s RETURNING tentativas_falhas;
                """, (usuario["id"],))
                if cursor.fetchone()[0] >= TENTATIVAS_ANTES_DO_BLOQUEIO:
                    cursor.execute("""
                        UPDATE usuarios
                        SET bloqueado_ate = NOW() + make_interval(mins => %s), tentativas_falhas = 0
                        WHERE id = %s;
                    """, (MINUTOS_DE_BLOQUEIO, usuario["id"]))
                    auditar(cursor, usuario["empresa_id"], "login_bloqueado", alvo_id=usuario["id"],
                            detalhes={"tentativas": TENTATIVAS_ANTES_DO_BLOQUEIO,
                                      "minutos": MINUTOS_DE_BLOQUEIO})
                conexao.commit()
                return jsonify(CREDENCIAIS_INVALIDAS[0]), CREDENCIAIS_INVALIDAS[1]

            # Daqui em diante a senha está correta: as mensagens podem ser específicas
            if not usuario["ativo"]:
                return jsonify({
                    "error": "CONTA_DESATIVADA",
                    "erro": "Sua conta foi desativada. Fale com o gestor da sua empresa."
                }), 403

            if usuario["temporaria_expirada"]:
                return jsonify({
                    "error": "SENHA_TEMPORARIA_EXPIRADA",
                    "erro": "Sua senha temporária expirou. Peça ao gestor uma nova."
                }), 401

            # Janela checada só depois da senha: não revela horários a quem não autenticou
            if not usuario["dentro_janela"]:
                return resposta_horario_bloqueado(usuario["hora_inicio_acesso"],
                                                  usuario["hora_fim_acesso"])

            cursor.execute("""
                UPDATE usuarios
                SET tentativas_falhas = 0, bloqueado_ate = NULL, ultimo_login_em = NOW()
                WHERE id = %s;
            """, (usuario["id"],))
        conexao.commit()

    token = gerar_token(usuario["id"], usuario["empresa_id"], usuario["perfil"],
                        usuario["token_versao"])

    return jsonify({
        "mensagem": "Login realizado com sucesso!",
        "token": token,
        "usuario": montar_usuario(usuario)
    }), 200


@auth_bp.route("/me", methods=["GET"])
@token_obrigatorio
@permitir_com_senha_pendente
def meus_dados():
    """Somente os dados de quem está logado (substitui /auth/me/<id>, que era público)."""
    with get_db_connection() as conexao, conexao.cursor() as cursor:
        usuario = buscar_usuario(cursor, "u.id = %(id)s", {"id": g.usuario_id})

    return jsonify(montar_usuario(usuario)), 200


@auth_bp.route("/senha", methods=["PUT"])
@token_obrigatorio
@permitir_com_senha_pendente
def alterar_minha_senha():
    """Troca a própria senha (também conclui a troca obrigatória da senha temporária).

    Exige a senha atual. Encerra as outras sessões e devolve um token novo
    para a sessão atual continuar.
    """
    dados = request.get_json(silent=True) or {}
    senha_atual = dados.get("senha_atual")
    nova_senha = dados.get("nova_senha")

    if not isinstance(senha_atual, str) or not senha_atual:
        return jsonify({"erro": "Informe a senha atual."}), 400

    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            usuario = buscar_usuario(cursor, "u.id = %(id)s", {"id": g.usuario_id})

            # 400 (e não 401): o front trata 401 como sessão encerrada
            if not senha_confere(senha_atual, usuario["senha"]):
                return jsonify({"erro": "A senha atual não confere."}), 400

            problema = validar_senha(nova_senha, usuario["email"])
            if problema:
                return jsonify({"erro": problema}), 400

            if senha_confere(nova_senha, usuario["senha"]):
                return jsonify({"erro": "A nova senha precisa ser diferente da atual."}), 400

            cursor.execute("""
                UPDATE usuarios
                SET senha = %s, deve_trocar_senha = FALSE, senha_temporaria_expira_em = NULL,
                    senha_alterada_em = NOW(), token_versao = token_versao + 1,
                    tentativas_falhas = 0, bloqueado_ate = NULL
                WHERE id = %s
                RETURNING token_versao;
            """, (gerar_hash(nova_senha), g.usuario_id))
            nova_versao = cursor.fetchone()[0]

            auditar(cursor, g.empresa_id, "senha_alterada", ator_id=g.usuario_id, alvo_id=g.usuario_id,
                    detalhes={"era_temporaria": usuario["deve_trocar_senha"]})
        conexao.commit()

    usuario["deve_trocar_senha"] = False
    return jsonify({
        "mensagem": "Senha alterada com sucesso!",
        "token": gerar_token(g.usuario_id, g.empresa_id, g.perfil, nova_versao),
        "usuario": montar_usuario(usuario)
    }), 200
