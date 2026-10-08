from flask import Blueprint, jsonify

from database.conexao import conectar_banco


dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/dashboard"
)


@dashboard_bp.route("/<int:empresa_id>", methods=["GET"])
def buscar_dashboard(empresa_id):
    conexao = conectar_banco()
    cursor = conexao.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM clientes
        WHERE empresa_id = %s;
    """, (empresa_id,))

    total_clientes = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM oportunidades
        WHERE empresa_id = %s;
    """, (empresa_id,))

    total_oportunidades = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*)
        FROM oportunidades
        WHERE empresa_id = %s
        AND etapa = 'Fechado';
    """, (empresa_id,))

    vendas_fechadas = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COALESCE(SUM(valor), 0)
        FROM oportunidades
        WHERE empresa_id = %s
        AND etapa = 'Fechado';
    """, (empresa_id,))

    receita_total = cursor.fetchone()[0]

    cursor.close()
    conexao.close()

    return jsonify({
        "total_clientes": total_clientes,
        "total_oportunidades": total_oportunidades,
        "vendas_fechadas": vendas_fechadas,
        "receita_total": float(receita_total)
    }), 200