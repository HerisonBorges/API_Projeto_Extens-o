"""Monitoramento.

GET /health          liveness: o processo responde. NÃO toca no banco, para a
                     plataforma não reiniciar a API quando só o banco oscila.
GET /health/pronto   readiness: o banco responde (SELECT 1). 503 se não.

Sem autenticação e sem detalhes internos na resposta (o erro vai só para o log).
"""
import time

from flask import Blueprint, current_app, jsonify

from database.conexao import get_db_connection


health_bp = Blueprint("health", __name__, url_prefix="/health")


@health_bp.route("", methods=["GET"])
def liveness():
    return jsonify({"status": "ok"}), 200


@health_bp.route("/pronto", methods=["GET"])
def readiness():
    inicio = time.monotonic()
    try:
        with get_db_connection() as conexao, conexao.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
    except Exception:  # noqa: BLE001 - qualquer falha = indisponível
        current_app.logger.exception("Readiness: banco indisponível")
        return jsonify({"status": "indisponivel", "banco": "erro"}), 503

    return jsonify({
        "status": "ok",
        "banco": "ok",
        "latencia_ms": round((time.monotonic() - inicio) * 1000)
    }), 200
