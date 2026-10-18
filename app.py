from flask import Flask

from flasgger import Swagger

from routes.auth import auth_bp
from routes.clientes import clientes_bp
from routes.configuracoes import configuracoes_bp
from routes.dashboard import dashboard_bp
from routes.oportunidades import oportunidades_bp
from routes.tarefas import tarefas_bp
from routes.relatorios import relatorios_bp

app = Flask(__name__)

swagger = Swagger(app)

app.register_blueprint(auth_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(configuracoes_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(oportunidades_bp)
app.register_blueprint(tarefas_bp)
app.register_blueprint(relatorios_bp)

if __name__ == "__main__":
    app.run(debug=True)
