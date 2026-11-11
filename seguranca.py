import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import g, jsonify, request

from database.conexao import conectar_banco


EXPIRACAO_HORAS = 8


def _chave():
    """Lida a cada uso, sem valor padrão: config.validar_configuracao() garante,
    na subida da API, que a chave existe e é forte. Scripts que não usam JWT
    (ex.: o worker) não precisam dela."""
    chave = os.environ.get("SECRET_KEY")
    if not chave:
        raise RuntimeError("SECRET_KEY não definida.")
    return chave

# Fuso usado para a janela de acesso. O servidor do banco roda em UTC.
TZ_EMPRESA = os.environ.get("TZ_EMPRESA", "America/Sao_Paulo")

# Expressão SQL: o usuário está dentro da janela de acesso agora?
# - NULL = irrestrito
# - início < fim: janela no mesmo dia, fim exclusivo
# - início > fim: janela que cruza a meia-noite
# Requer o parâmetro nomeado %(tz)s.
SQL_DENTRO_JANELA = """
    CASE
        WHEN hora_inicio_acesso IS NULL OR hora_fim_acesso IS NULL THEN TRUE
        WHEN hora_inicio_acesso < hora_fim_acesso THEN
            (NOW() AT TIME ZONE %(tz)s)::time >= hora_inicio_acesso
            AND (NOW() AT TIME ZONE %(tz)s)::time < hora_fim_acesso
        ELSE
            (NOW() AT TIME ZONE %(tz)s)::time >= hora_inicio_acesso
            OR (NOW() AT TIME ZONE %(tz)s)::time < hora_fim_acesso
    END
"""


def formatar_hora(valor):
    return valor.strftime("%H:%M") if valor is not None else None


def resposta_horario_bloqueado(hora_inicio, hora_fim):
    return jsonify({
        "error": "HORARIO_BLOQUEADO",
        "message": (
            f"Acesso permitido apenas entre {formatar_hora(hora_inicio)} "
            f"e {formatar_hora(hora_fim)}"
        )
    }), 403


def gerar_token(usuario_id, empresa_id, perfil):
    payload = {
        "sub": str(usuario_id),
        "empresa_id": empresa_id,
        "perfil": perfil,
        "exp": datetime.now(timezone.utc) + timedelta(hours=EXPIRACAO_HORAS),
    }
    return jwt.encode(payload, _chave(), algorithm="HS256")


def carregar_acesso_usuario(usuario_id):
    """Retorna (empresa_id, perfil, hora_inicio, hora_fim, dentro_janela) ou None."""
    conexao = conectar_banco()
    try:
        with conexao.cursor() as cursor:
            cursor.execute(f"""
                SELECT empresa_id, perfil, hora_inicio_acesso, hora_fim_acesso,
                       {SQL_DENTRO_JANELA}
                FROM usuarios
                WHERE id = %(id)s;
            """, {"id": usuario_id, "tz": TZ_EMPRESA})
            return cursor.fetchone()
    finally:
        conexao.close()


def token_obrigatorio(funcao):
    """Exige JWT válido e janela de acesso aberta.

    empresa_id vem SEMPRE do token. Perfil e janela são relidos do banco a
    cada requisição, então mudanças feitas pelo Gestor valem na hora,
    mesmo com a sessão já aberta.
    """

    @wraps(funcao)
    def wrapper(*args, **kwargs):
        cabecalho = request.headers.get("Authorization", "")

        if not cabecalho.startswith("Bearer "):
            return jsonify({"erro": "Token ausente."}), 401

        try:
            payload = jwt.decode(
                cabecalho[7:], _chave(), algorithms=["HS256"]
            )
        except jwt.ExpiredSignatureError:
            return jsonify({"erro": "Token expirado."}), 401
        except jwt.InvalidTokenError:
            return jsonify({"erro": "Token inválido."}), 401

        usuario_id = int(payload["sub"])
        acesso = carregar_acesso_usuario(usuario_id)

        # Usuário removido ou movido de empresa: o token deixa de valer
        if not acesso or acesso[0] != payload["empresa_id"]:
            return jsonify({"erro": "Usuário inválido."}), 401

        empresa_id, perfil, hora_inicio, hora_fim, dentro_janela = acesso

        if not dentro_janela:
            return resposta_horario_bloqueado(hora_inicio, hora_fim)

        g.usuario_id = usuario_id
        g.empresa_id = empresa_id
        g.perfil = perfil

        return funcao(*args, **kwargs)

    return wrapper


# Alias com o nome usado na especificação
token_required = token_obrigatorio


def perfil_requerido(*perfis):
    """Usar depois de @token_obrigatorio."""

    def decorador(funcao):
        @wraps(funcao)
        def wrapper(*args, **kwargs):
            if g.perfil not in perfis:
                return jsonify({"erro": "Acesso negado para este perfil."}), 403
            return funcao(*args, **kwargs)

        return wrapper

    return decorador
