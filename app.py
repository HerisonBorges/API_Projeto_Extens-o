# Carrega o .env ANTES de importar os módulos que leem variáveis de ambiente
# (seguranca.py lê SECRET_KEY na importação).
from dotenv import load_dotenv

load_dotenv()

from flask import Flask  # noqa: E402

from flasgger import Swagger
from flask_cors import CORS

from database.conexao import devolver_conexoes_da_requisicao

from routes.auth import auth_bp
from routes.clientes import clientes_bp
from routes.configuracoes import configuracoes_bp
from routes.dashboard import dashboard_bp
from routes.oportunidades import oportunidades_bp
from routes.tarefas import tarefas_bp
from routes.relatorios import relatorios_bp
from routes.interacoes import interacoes_bp

app = Flask(__name__)

# Devolve ao pool conexões que uma rota não fechou (ex.: exceção no meio)
app.teardown_appcontext(devolver_conexoes_da_requisicao)

# Libera o acesso apenas para o front-end local (CRA na 3000, Vite na 5173)
CORS(app, resources={
    r"/*": {"origins": ["http://localhost:3000", "http://localhost:5173"]}
})

swagger = Swagger(app)

app.register_blueprint(auth_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(configuracoes_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(oportunidades_bp)
app.register_blueprint(tarefas_bp)
app.register_blueprint(relatorios_bp)
app.register_blueprint(interacoes_bp)

if __name__ == "__main__":
    app.run(debug=True)
