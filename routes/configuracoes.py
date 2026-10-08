from flask import Blueprint, jsonify, request

from database.conexao import conectar_banco


configuracoes_bp = Blueprint(
    "configuracoes",
    __name__,
    url_prefix="/configuracoes"
)

@configuracoes_bp.route("/<int:empresa_id>", methods=["GET"])
def buscar_configuracoes(empresa_id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id, empresa_id, notificacoes_email, tema_escuro
        FROM configuracoes
        WHERE empresa_id = %s;
    """, (empresa_id,))

    configuracao = cursor.fetchone()

    cursor.close()
    conexao.close()

    if not configuracao:
        return jsonify({
            "erro": "Configurações não encontradas."
        }), 404

    return jsonify({
        "id": configuracao[0],
        "empresa_id": configuracao[1],
        "notificacoes_email": configuracao[2],
        "tema_escuro": configuracao[3]
    }), 200

@configuracoes_bp.route("/<int:empresa_id>", methods=["PUT"])
def atualizar_configuracoes(empresa_id):
    dados = request.get_json()

    notificacoes_email = dados.get("notificacoes_email", True)
    tema_escuro = dados.get("tema_escuro", True)

    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT id
        FROM configuracoes
        WHERE empresa_id = %s;
    """, (empresa_id,))

    configuracao = cursor.fetchone()

    if configuracao:
        cursor.execute("""
            UPDATE configuracoes
            SET notificacoes_email = %s,
                tema_escuro = %s
            WHERE empresa_id = %s;
        """, (notificacoes_email, tema_escuro, empresa_id))

        mensagem = "Configurações atualizadas com sucesso!"

    else:
        cursor.execute("""
            INSERT INTO configuracoes (
                empresa_id,
                notificacoes_email,
                tema_escuro
            )
            VALUES (%s, %s, %s);
        """, (empresa_id, notificacoes_email, tema_escuro))

        mensagem = "Configurações criadas com sucesso!"

    conexao.commit()

    cursor.close()
    conexao.close()

    return jsonify({
        "mensagem": mensagem
    }), 200