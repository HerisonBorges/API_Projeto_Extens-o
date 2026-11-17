"""Recorrências por cliente: "toda segunda", "todo dia 5".

O worker (database/worker_recorrencias.py) gera, em cada data, um follow-up
(tipo lembrete) ou uma oportunidade no funil (tipo oportunidade).

Regras de acesso:
  - empresa_id vem sempre do token; regra de outra empresa responde 404;
  - Gestor e Atendimento criam, alteram e pausam; só o Gestor exclui.
"""
from flask import Blueprint, g, jsonify, request

from database.conexao import get_db_connection
from recorrencia import descrever, hoje_na_empresa, proxima_ocorrencia, validar_recorrencia
from seguranca import fuso_empresa, perfil_requerido, token_obrigatorio


recorrencias_bp = Blueprint("recorrencias", __name__, url_prefix="/recorrencias")

SELECT_RECORRENCIAS = """
    SELECT r.id, r.empresa_id, r.cliente_id, c.nome, r.tipo, r.titulo, r.valor, r.notas,
           r.frequencia, r.dia_semana, r.dia_mes, r.proxima_execucao, r.ativo,
           r.criado_em, u.nome,
           (SELECT MAX(e.data_referencia) FROM recorrencia_execucoes e WHERE e.recorrencia_id = r.id)
    FROM recorrencias r
    JOIN clientes c ON c.id = r.cliente_id
    LEFT JOIN usuarios u ON u.id = r.criado_por
"""


def montar_recorrencia(r):
    return {
        "id": r[0],
        "empresa_id": r[1],
        "cliente_id": r[2],
        "cliente_nome": r[3],
        "tipo": r[4],
        "titulo": r[5],
        "valor": float(r[6]) if r[6] is not None else None,
        "notas": r[7],
        "frequencia": r[8],
        "dia_semana": r[9],
        "dia_mes": r[10],
        "descricao": descrever(r[8], r[9], r[10]),
        "proxima_execucao": r[11].isoformat(),
        "ativo": r[12],
        "criado_em": r[13].isoformat() if r[13] else None,
        "criado_por_nome": r[14],
        "ultima_execucao": r[15].isoformat() if r[15] else None,
    }


def buscar(cursor, id, empresa_id):
    cursor.execute(f"{SELECT_RECORRENCIAS} WHERE r.id = %s AND r.empresa_id = %s;", (id, empresa_id))
    linha = cursor.fetchone()
    return montar_recorrencia(linha) if linha else None


def inserir_recorrencia(cursor, empresa_id, cliente_id, campos, usuario_id, hoje):
    """INSERT compartilhado com a importação e com POST /oportunidades."""
    proxima = proxima_ocorrencia(campos["frequencia"], campos["dia_semana"], campos["dia_mes"], hoje)
    cursor.execute("""
        INSERT INTO recorrencias (empresa_id, cliente_id, tipo, titulo, valor, notas,
                                  frequencia, dia_semana, dia_mes, proxima_execucao, criado_por)
        VALUES (%(empresa_id)s, %(cliente_id)s, %(tipo)s, %(titulo)s, %(valor)s, %(notas)s,
                %(frequencia)s, %(dia_semana)s, %(dia_mes)s, %(proxima)s, %(usuario_id)s)
        RETURNING id;
    """, {**campos, "empresa_id": empresa_id, "cliente_id": cliente_id,
          "proxima": proxima, "usuario_id": usuario_id})
    return cursor.fetchone()[0]


def _cliente_id(dados):
    valor = dados.get("cliente_id")
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor


@recorrencias_bp.route("", methods=["GET"])
@token_obrigatorio
def listar_recorrencias():
    cliente_id = request.args.get("cliente_id", type=int)
    with get_db_connection() as conexao, conexao.cursor() as cursor:
        if cliente_id is not None:
            cursor.execute(f"{SELECT_RECORRENCIAS} WHERE r.empresa_id = %s AND r.cliente_id = %s "
                           "ORDER BY r.ativo DESC, r.proxima_execucao;", (g.empresa_id, cliente_id))
        else:
            cursor.execute(f"{SELECT_RECORRENCIAS} WHERE r.empresa_id = %s "
                           "ORDER BY r.ativo DESC, r.proxima_execucao;", (g.empresa_id,))
        return jsonify([montar_recorrencia(r) for r in cursor.fetchall()]), 200


@recorrencias_bp.route("", methods=["POST"])
@token_obrigatorio
def criar_recorrencia():
    dados = request.get_json(silent=True) or {}
    cliente_id = _cliente_id(dados)
    if cliente_id is None:
        return jsonify({"erro": "cliente_id é obrigatório."}), 400
    campos, erro = validar_recorrencia(dados)
    if erro:
        return jsonify({"erro": erro}), 400

    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT 1 FROM clientes WHERE id = %s AND empresa_id = %s;",
                           (cliente_id, g.empresa_id))
            if not cursor.fetchone():
                return jsonify({"erro": "Cliente não encontrado."}), 404
            hoje = hoje_na_empresa(cursor, fuso_empresa())
            novo_id = inserir_recorrencia(cursor, g.empresa_id, cliente_id, campos, g.usuario_id, hoje)
            recorrencia = buscar(cursor, novo_id, g.empresa_id)
        conexao.commit()

    return jsonify({"mensagem": "Recorrência criada.", "recorrencia": recorrencia}), 201


@recorrencias_bp.route("/<int:id>", methods=["PUT"])
@token_obrigatorio
def alterar_recorrencia(id):
    """Substitui a regra. A próxima data é recalculada a partir de hoje."""
    campos, erro = validar_recorrencia(request.get_json(silent=True) or {})
    if erro:
        return jsonify({"erro": erro}), 400

    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            hoje = hoje_na_empresa(cursor, fuso_empresa())
            proxima = proxima_ocorrencia(campos["frequencia"], campos["dia_semana"], campos["dia_mes"], hoje)
            # Não gera de novo uma data que já foi gerada hoje para esta regra
            cursor.execute("""
                SELECT 1 FROM recorrencia_execucoes
                WHERE recorrencia_id = %s AND empresa_id = %s AND data_referencia = %s;
            """, (id, g.empresa_id, proxima))
            if cursor.fetchone():
                proxima = proxima_ocorrencia(campos["frequencia"], campos["dia_semana"], campos["dia_mes"],
                                             proxima, incluir_o_dia=False)
            cursor.execute("""
                UPDATE recorrencias
                SET tipo = %(tipo)s, titulo = %(titulo)s, valor = %(valor)s, notas = %(notas)s,
                    frequencia = %(frequencia)s, dia_semana = %(dia_semana)s, dia_mes = %(dia_mes)s,
                    proxima_execucao = %(proxima)s, atualizado_em = NOW()
                WHERE id = %(id)s AND empresa_id = %(empresa_id)s;
            """, {**campos, "proxima": proxima, "id": id, "empresa_id": g.empresa_id})
            if cursor.rowcount == 0:
                return jsonify({"erro": "Recorrência não encontrada."}), 404
            recorrencia = buscar(cursor, id, g.empresa_id)
        conexao.commit()

    return jsonify({"mensagem": "Recorrência atualizada.", "recorrencia": recorrencia}), 200


@recorrencias_bp.route("/<int:id>/ativo", methods=["PATCH"])
@token_obrigatorio
def ativar_recorrencia(id):
    """Pausa ou retoma. Ao retomar, conta a partir de hoje: datas do período
    pausado não são geradas depois."""
    ativo = (request.get_json(silent=True) or {}).get("ativo")
    if not isinstance(ativo, bool):
        return jsonify({"erro": "ativo deve ser true ou false."}), 400

    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            atual = buscar(cursor, id, g.empresa_id)
            if not atual:
                return jsonify({"erro": "Recorrência não encontrada."}), 404
            proxima = atual["proxima_execucao"]
            if ativo and not atual["ativo"]:
                hoje = hoje_na_empresa(cursor, fuso_empresa())
                proxima = proxima_ocorrencia(atual["frequencia"], atual["dia_semana"], atual["dia_mes"], hoje)
            cursor.execute("""
                UPDATE recorrencias SET ativo = %s, proxima_execucao = %s, atualizado_em = NOW()
                WHERE id = %s AND empresa_id = %s;
            """, (ativo, proxima, id, g.empresa_id))
            recorrencia = buscar(cursor, id, g.empresa_id)
        conexao.commit()

    return jsonify({"mensagem": "Recorrência retomada." if ativo else "Recorrência pausada.",
                    "recorrencia": recorrencia}), 200


@recorrencias_bp.route("/<int:id>", methods=["DELETE"])
@token_obrigatorio
@perfil_requerido("Gestor")
def excluir_recorrencia(id):
    """Exclui a regra. Follow-ups e oportunidades já gerados continuam."""
    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute("DELETE FROM recorrencias WHERE id = %s AND empresa_id = %s;", (id, g.empresa_id))
            if cursor.rowcount == 0:
                return jsonify({"erro": "Recorrência não encontrada."}), 404
        conexao.commit()
    return jsonify({"mensagem": "Recorrência excluída."}), 200
