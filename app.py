# Carrega o .env ANTES de importar os módulos que leem variáveis de ambiente.
# Em produção (PaaS) não há .env: as variáveis vêm do painel e isto não faz nada.
from dotenv import load_dotenv

load_dotenv()

import logging  # noqa: E402
import os  # noqa: E402

from flask import Flask, jsonify  # noqa: E402
from flasgger import Swagger  # noqa: E402
from flask_cors import CORS  # noqa: E402
from werkzeug.exceptions import HTTPException  # noqa: E402
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402

from config import em_producao, origens_cors, validar_configuracao  # noqa: E402

# Falha já na subida se faltar SECRET_KEY forte, DB_PASSWORD ou CORS de produção
validar_configuracao()

from database.conexao import devolver_conexoes_da_requisicao  # noqa: E402
from routes.auth import auth_bp  # noqa: E402
from routes.clientes import clientes_bp  # noqa: E402
from routes.configuracoes import configuracoes_bp  # noqa: E402
from routes.dashboard import dashboard_bp  # noqa: E402
from routes.health import health_bp  # noqa: E402
from routes.interacoes import interacoes_bp  # noqa: E402
from routes.oportunidades import oportunidades_bp  # noqa: E402
from routes.relatorios import relatorios_bp  # noqa: E402
from routes.tarefas import tarefas_bp  # noqa: E402

PRODUCAO = em_producao()

app = Flask(__name__)
app.json.ensure_ascii = False  # "Ligação" e não "Liga\u00e7\u00e3o"

if PRODUCAO:
    # Atrás do proxy do PaaS: IP e esquema (https) reais vêm dos cabeçalhos X-Forwarded-*
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Devolve ao pool conexões que uma rota não fechou (ex.: exceção no meio)
app.teardown_appcontext(devolver_conexoes_da_requisicao)

# Desenvolvimento: front local. Produção: somente as origens de CORS_ORIGINS.
CORS(app, resources={r"/*": {"origins": origens_cors()}})

# Documentação interativa expõe o mapa da API: desligada em produção por padrão
if not PRODUCAO or os.getenv("SWAGGER_ATIVO") == "1":
    Swagger(app)

for blueprint in (
    health_bp,
    auth_bp,
    clientes_bp,
    configuracoes_bp,
    dashboard_bp,
    oportunidades_bp,
    tarefas_bp,
    relatorios_bp,
    interacoes_bp,
):
    app.register_blueprint(blueprint)


MENSAGENS_HTTP = {
    400: "Requisição inválida.",
    404: "Rota não encontrada.",
    405: "Método não permitido para esta rota.",
    413: "Requisição grande demais.",
    415: "Envie o corpo em JSON.",
}


# Respostas de erro sempre em JSON (o front lê o campo "erro")
@app.errorhandler(HTTPException)
def erro_http(erro):
    return jsonify({"erro": MENSAGENS_HTTP.get(erro.code, erro.description)}), erro.code


@app.errorhandler(Exception)
def erro_inesperado(erro):
    # Detalhes só no log; o cliente recebe uma mensagem genérica
    app.logger.exception("Erro não tratado: %s", erro)
    return jsonify({"erro": "Erro interno do servidor."}), 500


if __name__ == "__main__":
    # Só para desenvolvimento. Em produção: gunicorn (ver gunicorn.conf.py)
    app.run(
        debug=os.getenv("FLASK_DEBUG") == "1" and not PRODUCAO,
        port=int(os.getenv("PORT", "5000")),
    )
