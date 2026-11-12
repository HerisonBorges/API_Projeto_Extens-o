"""Gestão de usuários (IAM). Somente Gestor, sempre na empresa do token.

Regras:
  - Ninguém altera o próprio perfil nem desativa/redefine a si mesmo pelo
    painel (troca da própria senha é em PUT /auth/senha). Assim não há
    autoelevação de privilégio e a empresa nunca fica sem Gestor ativo.
  - Contas são desativadas, nunca apagadas (rastreabilidade).
  - Criação, redefinição e reativação geram senha temporária: mostrada uma
    única vez na resposta, vale 72h e obriga a troca no primeiro acesso.
  - Mudança de perfil, redefinição, desativação e reativação incrementam
    token_versao: sessões abertas do usuário afetado caem na hora.
  - Toda ação gera registro em auditoria_usuarios, na mesma transação.
"""
from flask import Blueprint, g, jsonify, request
from psycopg2 import errors

from database.conexao import get_db_connection
from iam import (
    PERFIS,
    SENHA_TEMPORARIA_HORAS,
    auditar,
    gerar_hash,
    gerar_senha_temporaria,
    normalizar_email,
    validar_email,
    validar_nome,
)
from seguranca import SQL_DENTRO_JANELA, TZ_EMPRESA, formatar_hora, perfil_requerido, token_obrigatorio


usuarios_bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

SELECT_USUARIOS = f"""
    SELECT id, nome, email, perfil, ativo, deve_trocar_senha,
           (bloqueado_ate IS NOT NULL AND bloqueado_ate > NOW()) AS bloqueado,
           hora_inicio_acesso, hora_fim_acesso, {SQL_DENTRO_JANELA} AS acesso_permitido,
           ultimo_login_em, senha_temporaria_expira_em
    FROM usuarios
"""

DETALHE_SENHA_TEMPORARIA = (
    f"Senha temporária válida por {SENHA_TEMPORARIA_HORAS}h. Entregue por um canal seguro "
    "(não por e-mail aberto ou grupo). Ela não será mostrada de novo."
)


def montar(u):
    return {
        "id": u[0],
        "nome": u[1],
        "email": u[2],
        "perfil": u[3],
        "ativo": u[4],
        "deve_trocar_senha": u[5],
        "bloqueado": u[6],
        "hora_inicio_acesso": formatar_hora(u[7]),
        "hora_fim_acesso": formatar_hora(u[8]),
        "acesso_permitido": u[9],
        "ultimo_login_em": u[10].isoformat() if u[10] else None,
        "senha_temporaria_expira_em": u[11].isoformat() if u[11] else None,
    }


def buscar(cursor, usuario_id, travar=False):
    cursor.execute(f"""
        {SELECT_USUARIOS}
        WHERE id = %(id)s AND empresa_id = %(empresa_id)s
        {"FOR UPDATE" if travar else ""};
    """, {"id": usuario_id, "empresa_id": g.empresa_id, "tz": TZ_EMPRESA})
    return cursor.fetchone()


def nao_encontrado():
    return jsonify({"erro": "Usuário não encontrado."}), 404


def proibido_em_si_mesmo(acao):
    return jsonify({"erro": f"Você não pode {acao} a sua própria conta. Peça a outro gestor."}), 409


@usuarios_bp.route("", methods=["GET"])
@token_obrigatorio
@perfil_requerido("Gestor")
def listar():
    with get_db_connection() as conexao, conexao.cursor() as cursor:
        cursor.execute(f"{SELECT_USUARIOS} WHERE empresa_id = %(empresa_id)s ORDER BY ativo DESC, nome, id;",
                       {"empresa_id": g.empresa_id, "tz": TZ_EMPRESA})
        return jsonify([montar(u) for u in cursor.fetchall()]), 200


@usuarios_bp.route("", methods=["POST"])
@token_obrigatorio
@perfil_requerido("Gestor")
def criar():
    dados = request.get_json(silent=True) or {}
    nome = dados.get("nome")
    email = normalizar_email(dados.get("email"))
    perfil = dados.get("perfil", "Atendimento")

    problema = validar_nome(nome) or validar_email(email)
    if problema:
        return jsonify({"erro": problema}), 400
    if perfil not in PERFIS:
        return jsonify({"erro": f"Perfil inválido. Use um de: {list(PERFIS)}"}), 400

    senha_temporaria = gerar_senha_temporaria()

    with get_db_connection() as conexao:
        try:
            with conexao.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO usuarios (empresa_id, nome, email, senha, perfil,
                                          deve_trocar_senha, senha_temporaria_expira_em)
                    VALUES (%s, %s, %s, %s, %s, TRUE, NOW() + make_interval(hours => %s))
                    RETURNING id;
                """, (g.empresa_id, nome.strip(), email, gerar_hash(senha_temporaria), perfil,
                      SENHA_TEMPORARIA_HORAS))
                novo_id = cursor.fetchone()[0]
                auditar(cursor, g.empresa_id, "usuario_criado", ator_id=g.usuario_id, alvo_id=novo_id,
                        detalhes={"perfil": perfil})
                usuario = buscar(cursor, novo_id)
            conexao.commit()
        except errors.UniqueViolation:
            conexao.rollback()
            return jsonify({"erro": "Este e-mail já está em uso."}), 409

    return jsonify({
        "mensagem": "Usuário criado.",
        "usuario": montar(usuario),
        "senha_temporaria": senha_temporaria,
        "aviso": DETALHE_SENHA_TEMPORARIA,
    }), 201


@usuarios_bp.route("/<int:id>", methods=["PUT"])
@token_obrigatorio
@perfil_requerido("Gestor")
def alterar(id):
    """Altera nome, e-mail e/ou perfil (campos omitidos ficam como estão)."""
    dados = request.get_json(silent=True) or {}
    campos = {}

    if "nome" in dados:
        problema = validar_nome(dados["nome"])
        if problema:
            return jsonify({"erro": problema}), 400
        campos["nome"] = dados["nome"].strip()

    if "email" in dados:
        email = normalizar_email(dados["email"])
        problema = validar_email(email)
        if problema:
            return jsonify({"erro": problema}), 400
        campos["email"] = email

    if "perfil" in dados:
        if dados["perfil"] not in PERFIS:
            return jsonify({"erro": f"Perfil inválido. Use um de: {list(PERFIS)}"}), 400
        campos["perfil"] = dados["perfil"]

    if not campos:
        return jsonify({"erro": "Informe nome, email ou perfil."}), 400

    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            atual = buscar(cursor, id, travar=True)
            if not atual:
                return nao_encontrado()

            mudou_perfil = "perfil" in campos and campos["perfil"] != atual[3]
            if mudou_perfil and id == g.usuario_id:
                return proibido_em_si_mesmo("alterar o perfil de")

            alteracoes = {k: v for k, v in campos.items()
                          if v != {"nome": atual[1], "email": atual[2], "perfil": atual[3]}[k]}
            if not alteracoes:
                return jsonify({"mensagem": "Nada a alterar.", "usuario": montar(atual)}), 200

            atribuicoes = ", ".join(f"{coluna} = %({coluna})s" for coluna in alteracoes)
            if mudou_perfil:
                atribuicoes += ", token_versao = token_versao + 1"

            try:
                cursor.execute(f"""
                    UPDATE usuarios SET {atribuicoes}
                    WHERE id = %(id)s AND empresa_id = %(empresa_id)s;
                """, {**alteracoes, "id": id, "empresa_id": g.empresa_id})
            except errors.UniqueViolation:
                conexao.rollback()
                return jsonify({"erro": "Este e-mail já está em uso."}), 409

            if mudou_perfil:
                auditar(cursor, g.empresa_id, "perfil_alterado", ator_id=g.usuario_id, alvo_id=id,
                        detalhes={"de": atual[3], "para": campos["perfil"]})
            outros = sorted(set(alteracoes) - {"perfil"})
            if outros:
                auditar(cursor, g.empresa_id, "usuario_alterado", ator_id=g.usuario_id, alvo_id=id,
                        detalhes={"campos": outros})

            usuario = buscar(cursor, id)
        conexao.commit()

    return jsonify({"mensagem": "Usuário atualizado.", "usuario": montar(usuario)}), 200


def _emitir_senha_temporaria(id, acao_auditoria, reativar):
    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            atual = buscar(cursor, id, travar=True)
            if not atual:
                return nao_encontrado()
            if id == g.usuario_id:
                return proibido_em_si_mesmo("redefinir a senha de" if not reativar else "reativar")
            if reativar and atual[4]:
                return jsonify({"erro": "Este usuário já está ativo."}), 409
            if not reativar and not atual[4]:
                return jsonify({"erro": "Usuário desativado. Use Reativar."}), 409

            senha_temporaria = gerar_senha_temporaria()
            cursor.execute("""
                UPDATE usuarios
                SET senha = %s, deve_trocar_senha = TRUE,
                    senha_temporaria_expira_em = NOW() + make_interval(hours => %s),
                    token_versao = token_versao + 1, tentativas_falhas = 0, bloqueado_ate = NULL,
                    ativo = TRUE, desativado_em = NULL
                WHERE id = %s AND empresa_id = %s;
            """, (gerar_hash(senha_temporaria), SENHA_TEMPORARIA_HORAS, id, g.empresa_id))
            auditar(cursor, g.empresa_id, acao_auditoria, ator_id=g.usuario_id, alvo_id=id)
            usuario = buscar(cursor, id)
        conexao.commit()

    return jsonify({
        "mensagem": "Usuário reativado." if reativar else "Senha redefinida.",
        "usuario": montar(usuario),
        "senha_temporaria": senha_temporaria,
        "aviso": DETALHE_SENHA_TEMPORARIA,
    }), 200


@usuarios_bp.route("/<int:id>/redefinir-senha", methods=["POST"])
@token_obrigatorio
@perfil_requerido("Gestor")
def redefinir_senha(id):
    """Gera senha temporária, desbloqueia a conta e encerra as sessões dela."""
    return _emitir_senha_temporaria(id, "senha_redefinida", reativar=False)


@usuarios_bp.route("/<int:id>/reativar", methods=["POST"])
@token_obrigatorio
@perfil_requerido("Gestor")
def reativar(id):
    """Reativa SEMPRE com senha nova: a antiga pode ter vazado enquanto a conta estava parada."""
    return _emitir_senha_temporaria(id, "usuario_reativado", reativar=True)


@usuarios_bp.route("/<int:id>/desativar", methods=["POST"])
@token_obrigatorio
@perfil_requerido("Gestor")
def desativar(id):
    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            atual = buscar(cursor, id, travar=True)
            if not atual:
                return nao_encontrado()
            if id == g.usuario_id:
                return proibido_em_si_mesmo("desativar")
            if not atual[4]:
                return jsonify({"erro": "Este usuário já está desativado."}), 409

            cursor.execute("""
                UPDATE usuarios
                SET ativo = FALSE, desativado_em = NOW(), token_versao = token_versao + 1
                WHERE id = %s AND empresa_id = %s;
            """, (id, g.empresa_id))
            auditar(cursor, g.empresa_id, "usuario_desativado", ator_id=g.usuario_id, alvo_id=id)
            usuario = buscar(cursor, id)
        conexao.commit()

    return jsonify({"mensagem": "Usuário desativado. As sessões dele foram encerradas.",
                    "usuario": montar(usuario)}), 200


@usuarios_bp.route("/auditoria", methods=["GET"])
@token_obrigatorio
@perfil_requerido("Gestor")
def auditoria():
    limite = request.args.get("limite", default=50, type=int)
    if not 1 <= limite <= 200:
        return jsonify({"erro": "limite deve estar entre 1 e 200."}), 400

    with get_db_connection() as conexao, conexao.cursor() as cursor:
        cursor.execute("""
            SELECT a.id, a.acao, a.detalhes, a.criado_em, a.ator_id, ator.nome, a.alvo_id, alvo.nome
            FROM auditoria_usuarios a
            LEFT JOIN usuarios ator ON ator.id = a.ator_id
            LEFT JOIN usuarios alvo ON alvo.id = a.alvo_id
            WHERE a.empresa_id = %s
            ORDER BY a.criado_em DESC, a.id DESC
            LIMIT %s;
        """, (g.empresa_id, limite))
        eventos = [
            {"id": e[0], "acao": e[1], "detalhes": e[2], "criado_em": e[3].isoformat(),
             "ator_id": e[4], "ator_nome": e[5], "alvo_id": e[6], "alvo_nome": e[7]}
            for e in cursor.fetchall()
        ]

    return jsonify(eventos), 200
