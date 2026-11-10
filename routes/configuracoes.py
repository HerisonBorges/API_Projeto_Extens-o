from datetime import datetime

from flask import Blueprint, g, jsonify, request

from database.conexao import conectar_banco
from seguranca import (
    SQL_DENTRO_JANELA,
    TZ_EMPRESA,
    formatar_hora,
    perfil_requerido,
    token_obrigatorio,
)


configuracoes_bp = Blueprint(
    "configuracoes",
    __name__,
    url_prefix="/configuracoes"
)

# Valores usados quando a empresa ainda não tem linha em configuracoes.
# dias_alerta_orcamento = 7 dias corridos (decisão do RF04).
PADRAO = {
    "notificacoes_email": True,
    "tema_escuro": True,
    "dias_alerta_orcamento": 7
}


def inteiro_positivo(valor):
    # bool é subclasse de int em Python: True não pode passar como 1
    return isinstance(valor, int) and not isinstance(valor, bool) and valor > 0


@configuracoes_bp.route("", methods=["GET"])
@token_obrigatorio
def obter_configuracoes():
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT notificacoes_email, tema_escuro, dias_alerta_orcamento
        FROM configuracoes
        WHERE empresa_id = %s;
    """, (g.empresa_id,))

    config = cursor.fetchone()

    cursor.close()
    conexao.close()

    if not config:
        return jsonify({"empresa_id": g.empresa_id, **PADRAO}), 200

    return jsonify({
        "empresa_id": g.empresa_id,
        "notificacoes_email": config[0],
        "tema_escuro": config[1],
        "dias_alerta_orcamento": config[2]
    }), 200


@configuracoes_bp.route("", methods=["PUT"])
@token_obrigatorio
@perfil_requerido("Gestor")
def atualizar_configuracoes():
    dados = request.get_json(silent=True) or {}

    campos = {}

    if "dias_alerta_orcamento" in dados:
        if not inteiro_positivo(dados["dias_alerta_orcamento"]):
            return jsonify({
                "erro": "dias_alerta_orcamento deve ser um número inteiro positivo."
            }), 400
        campos["dias_alerta_orcamento"] = dados["dias_alerta_orcamento"]

    for chave in ("notificacoes_email", "tema_escuro"):
        if chave in dados:
            if not isinstance(dados[chave], bool):
                return jsonify({
                    "erro": f"{chave} deve ser true ou false."
                }), 400
            campos[chave] = dados[chave]

    if not campos:
        return jsonify({
            "erro": "Informe ao menos um campo para atualizar."
        }), 400

    # Campos não enviados mantêm o valor atual (ou o padrão, se for a 1ª vez)
    valores = {**PADRAO, **campos}

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO configuracoes (
            empresa_id, notificacoes_email, tema_escuro, dias_alerta_orcamento
        )
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (empresa_id) DO UPDATE SET
            notificacoes_email = CASE WHEN %s THEN EXCLUDED.notificacoes_email
                                      ELSE configuracoes.notificacoes_email END,
            tema_escuro = CASE WHEN %s THEN EXCLUDED.tema_escuro
                               ELSE configuracoes.tema_escuro END,
            dias_alerta_orcamento = CASE WHEN %s THEN EXCLUDED.dias_alerta_orcamento
                                         ELSE configuracoes.dias_alerta_orcamento END
        RETURNING notificacoes_email, tema_escuro, dias_alerta_orcamento;
    """, (
        g.empresa_id,
        valores["notificacoes_email"],
        valores["tema_escuro"],
        valores["dias_alerta_orcamento"],
        "notificacoes_email" in campos,
        "tema_escuro" in campos,
        "dias_alerta_orcamento" in campos
    ))

    resultado = cursor.fetchone()

    conexao.commit()

    cursor.close()
    conexao.close()

    return jsonify({
        "mensagem": "Configurações atualizadas com sucesso!",
        "notificacoes_email": resultado[0],
        "tema_escuro": resultado[1],
        "dias_alerta_orcamento": resultado[2]
    }), 200


# ---------------------------------------------------------------------------
# Janela de acesso por usuário (RBAC estendido)
# ---------------------------------------------------------------------------

def montar_usuario_acesso(u):
    return {
        "id": u[0],
        "nome": u[1],
        "email": u[2],
        "perfil": u[3],
        "hora_inicio_acesso": formatar_hora(u[4]),
        "hora_fim_acesso": formatar_hora(u[5]),
        "acesso_permitido": u[6]
    }


def ler_hora(valor):
    """Aceita 'HH:MM' ou 'HH:MM:SS'. Retorna time ou None se inválido."""
    if not isinstance(valor, str):
        return None

    for formato in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(valor, formato).time()
        except ValueError:
            continue

    return None


@configuracoes_bp.route("/usuarios", methods=["GET"])
@token_obrigatorio
@perfil_requerido("Gestor")
def listar_usuarios_acesso():
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(f"""
        SELECT id, nome, email, perfil, hora_inicio_acesso, hora_fim_acesso,
               {SQL_DENTRO_JANELA}
        FROM usuarios
        WHERE empresa_id = %(empresa_id)s
        ORDER BY nome, id;
    """, {"empresa_id": g.empresa_id, "tz": TZ_EMPRESA})

    usuarios = [montar_usuario_acesso(u) for u in cursor.fetchall()]

    cursor.close()
    conexao.close()

    return jsonify(usuarios), 200


@configuracoes_bp.route("/usuarios/<int:id>", methods=["PUT"])
@token_obrigatorio
@perfil_requerido("Gestor")
def atualizar_horario_usuario(id):
    dados = request.get_json(silent=True) or {}

    if "hora_inicio_acesso" not in dados or "hora_fim_acesso" not in dados:
        return jsonify({
            "erro": "Envie hora_inicio_acesso e hora_fim_acesso "
                    "(os dois null = acesso irrestrito)."
        }), 400

    inicio_bruto = dados["hora_inicio_acesso"]
    fim_bruto = dados["hora_fim_acesso"]

    if inicio_bruto is None and fim_bruto is None:
        inicio, fim = None, None
    elif inicio_bruto is None or fim_bruto is None:
        return jsonify({
            "erro": "Informe os dois horários ou deixe os dois em branco."
        }), 400
    else:
        inicio, fim = ler_hora(inicio_bruto), ler_hora(fim_bruto)

        if inicio is None or fim is None:
            return jsonify({
                "erro": "Horário inválido. Use o formato HH:MM (00:00 a 23:59)."
            }), 400

        if inicio == fim:
            return jsonify({
                "erro": "Início e fim não podem ser iguais."
            }), 400

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute(f"""
        UPDATE usuarios
        SET hora_inicio_acesso = %(inicio)s,
            hora_fim_acesso = %(fim)s
        WHERE id = %(id)s AND empresa_id = %(empresa_id)s
        RETURNING id, nome, email, perfil, hora_inicio_acesso, hora_fim_acesso,
                  {SQL_DENTRO_JANELA};
    """, {
        "inicio": inicio,
        "fim": fim,
        "id": id,
        "empresa_id": g.empresa_id,
        "tz": TZ_EMPRESA
    })

    usuario = cursor.fetchone()

    if not usuario:
        conexao.rollback()
        cursor.close()
        conexao.close()
        return jsonify({"erro": "Usuário não encontrado."}), 404

    # Impede que o Gestor se tranque para fora da própria sessão
    if id == g.usuario_id and not usuario[6]:
        conexao.rollback()
        cursor.close()
        conexao.close()
        return jsonify({
            "erro": "Você não pode definir para si um horário que bloqueia "
                    "o seu acesso agora."
        }), 409

    conexao.commit()

    cursor.close()
    conexao.close()

    return jsonify({
        "mensagem": "Horário de acesso atualizado com sucesso!",
        "usuario": montar_usuario_acesso(usuario)
    }), 200
