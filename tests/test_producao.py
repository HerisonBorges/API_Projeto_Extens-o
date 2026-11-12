"""BDD: prontidão para produção (configuração, CORS, health, erros, Gunicorn).

    python3 -m unittest tests.test_producao -v

Os cenários que dependem de variáveis de ambiente rodam em subprocesso, com o
ambiente controlado, para não contaminar o processo dos outros testes.
"""
import json
import os
import socket
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path

from config import ler_origens_cors, origens_cors, problemas_de_configuracao

RAIZ = Path(__file__).resolve().parent.parent
CHAVE_FORTE = "k" * 48
BASE = {"SECRET_KEY": CHAVE_FORTE, "DB_PASSWORD": "x"}


def rodar_python(codigo, env_extra, timeout=60):
    """Executa código com o ambiente atual + env_extra (já com o .env carregado)."""
    env = {**os.environ, **env_extra}
    return subprocess.run([sys.executable, "-c", codigo], cwd=RAIZ, env=env,
                          capture_output=True, text=True, timeout=timeout)


class ValidacaoDeConfiguracao(unittest.TestCase):

    def test_01_chave_ausente_curta_ou_de_exemplo_bloqueia(self):
        """Dado SECRET_KEY ausente, curta ou de exemplo / Então a API não sobe."""
        for chave in ("", "curta", "troque-esta-chave-em-producao", "<chave-longa-e-aleatoria>"):
            with self.subTest(chave=chave):
                problemas = problemas_de_configuracao({**BASE, "SECRET_KEY": chave})
                self.assertTrue(any("SECRET_KEY" in p for p in problemas), problemas)

    def test_02_configuracao_minima_de_desenvolvimento_passa(self):
        self.assertEqual(problemas_de_configuracao(BASE), [])

    def test_03_producao_exige_cors_explicito(self):
        """Dado APP_ENV=producao sem CORS_ORIGINS / Então a API não sobe."""
        problemas = problemas_de_configuracao({**BASE, "APP_ENV": "producao"})
        self.assertTrue(any("CORS_ORIGINS" in p for p in problemas), problemas)

        ok = {**BASE, "APP_ENV": "producao", "CORS_ORIGINS": "https://sandro.netlify.app"}
        self.assertEqual(problemas_de_configuracao(ok), [])

    def test_04_app_env_invalido_bloqueia(self):
        problemas = problemas_de_configuracao({**BASE, "APP_ENV": "prod"})
        self.assertTrue(any("APP_ENV" in p for p in problemas), problemas)

    def test_05_parse_das_origens(self):
        self.assertEqual(
            ler_origens_cors(" https://a.app/ , https://b.app:8443 ,", producao=True),
            ["https://a.app", "https://b.app:8443"],
        )
        for invalida in ("*", "sandro.app", "https://a.app/caminho", "ftp://a.app"):
            with self.subTest(origem=invalida), self.assertRaises(ValueError):
                ler_origens_cors(invalida, producao=False)

        with self.assertRaises(ValueError):
            ler_origens_cors("http://sandro.app", producao=True)
        self.assertEqual(ler_origens_cors("http://localhost:5173", producao=True),
                         ["http://localhost:5173"])

    def test_06_desenvolvimento_sem_cors_usa_front_local(self):
        self.assertEqual(origens_cors(BASE), ["http://localhost:3000", "http://localhost:5173"])
        self.assertEqual(origens_cors({**BASE, "APP_ENV": "producao"}), [])

    def test_07_api_recusa_subir_sem_chave(self):
        """Dado o app importado sem SECRET_KEY / Então o processo falha com mensagem clara."""
        r = rodar_python("import app", {"SECRET_KEY": ""})
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("SECRET_KEY não definida", r.stderr)

    def test_08_worker_nao_depende_de_secret_key(self):
        """Dado SECRET_KEY vazia / Então o worker roda (não usa JWT)."""
        r = rodar_python(
            "from database import worker_reciclagem as w; raise SystemExit(w.main(['--dry-run', '--empresa', '-1']))",
            {"SECRET_KEY": ""})
        self.assertEqual(r.returncode, 0, r.stderr[-500:])
        self.assertIn("[dry-run] 0 reciclagem", r.stdout)


class ComportamentoEmProducao(unittest.TestCase):

    CODIGO = """
import json, app
c = app.app.test_client()
def preflight(origem):
    r = c.options('/oportunidades', headers={'Origin': origem, 'Access-Control-Request-Method': 'GET',
                                             'Access-Control-Request-Headers': 'Authorization'})
    return r.headers.get('Access-Control-Allow-Origin')
print(json.dumps({
    'debug': app.app.debug,
    'cors_netlify': preflight('https://sandro.netlify.app'),
    'cors_localhost': preflight('http://localhost:5173'),
    'cors_estranho': preflight('https://site-malicioso.example'),
    'swagger': c.get('/apidocs/').status_code,
    'health': c.get('/health').status_code,
    'https_atras_do_proxy': esquema_apos_proxy(),
}))
"""

    # O ProxyFix reescreve o environ WSGI no lugar: inspeciona depois da chamada
    PREPARO = """
from werkzeug.test import EnvironBuilder
def esquema_apos_proxy():
    environ = EnvironBuilder(path='/health', headers={'X-Forwarded-Proto': 'https',
                                                      'X-Forwarded-For': '203.0.113.7'}).get_environ()
    list(app.app.wsgi_app(environ, lambda *a: None))
    return environ['wsgi.url_scheme'] + '|' + environ['REMOTE_ADDR']
"""

    @classmethod
    def setUpClass(cls):
        codigo = cls.CODIGO.replace("c = app.app.test_client()",
                                    "c = app.app.test_client()\n" + cls.PREPARO)
        r = rodar_python(codigo, {"APP_ENV": "producao", "CORS_ORIGINS": "https://sandro.netlify.app"})
        assert r.returncode == 0, r.stderr[-800:]
        cls.res = json.loads(r.stdout.strip().splitlines()[-1])

    def test_01_debug_desligado(self):
        self.assertFalse(self.res["debug"])

    def test_02_cors_somente_origem_configurada(self):
        """Então só o front de produção recebe o cabeçalho CORS; localhost e terceiros não."""
        self.assertEqual(self.res["cors_netlify"], "https://sandro.netlify.app")
        self.assertIsNone(self.res["cors_localhost"])
        self.assertIsNone(self.res["cors_estranho"])

    def test_03_swagger_desligado(self):
        self.assertEqual(self.res["swagger"], 404)

    def test_04_proxy_fix_reconhece_https_e_ip_real(self):
        """Dado o proxy do PaaS / Então o app enxerga https e o IP real do cliente."""
        self.assertEqual(self.res["https_atras_do_proxy"], "https|203.0.113.7")


class HealthEErros(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import app as aplicacao
        cls.c = aplicacao.app.test_client()
        cls.app = aplicacao.app

    def test_01_liveness_nao_exige_token_nem_banco(self):
        r = self.c.get("/health")
        self.assertEqual((r.status_code, r.get_json()), (200, {"status": "ok"}))

    def test_02_readiness_consulta_o_banco(self):
        r = self.c.get("/health/pronto")
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["banco"], "ok")

    def test_03_readiness_503_sem_vazar_detalhes(self):
        """Dado o banco indisponível / Então 503 genérico, sem mensagem interna."""
        import routes.health as health
        original = health.get_db_connection

        def quebrado():
            raise RuntimeError("senha=segredo host=interno")

        health.get_db_connection = quebrado
        try:
            r = self.c.get("/health/pronto")
        finally:
            health.get_db_connection = original

        self.assertEqual(r.status_code, 503)
        self.assertNotIn("segredo", r.get_data(as_text=True))

    def test_04_erros_http_em_json_e_portugues(self):
        self.assertEqual(self.c.get("/nao-existe").get_json(), {"erro": "Rota não encontrada."})
        self.assertEqual(self.c.delete("/health").status_code, 405)

    def test_05_corpo_que_nao_e_json_recebe_erro_json(self):
        """Dado um login com corpo texto / Então 400 em JSON e português, sem traceback."""
        r = self.c.post("/auth/login", data="isto não é json", content_type="text/plain")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json(), {"erro": "E-mail e senha são obrigatórios."})
        self.assertNotIn("Traceback", r.get_data(as_text=True))

    def test_05b_415_continua_em_json_e_portugues(self):
        """Dado uma rota que exige JSON estrito / Então o 415 sai traduzido."""
        from werkzeug.exceptions import UnsupportedMediaType
        from app import erro_http
        with self.app.test_request_context("/"):
            resposta, codigo = erro_http(UnsupportedMediaType())
        self.assertEqual((codigo, resposta.get_json()), (415, {"erro": "Envie o corpo em JSON."}))

    def test_06_excecao_inesperada_vira_500_generico(self):
        """Dado uma exceção não tratada / Então 500 genérico; detalhe só no log."""
        from app import erro_inesperado
        with self.app.test_request_context("/"):
            resposta, codigo = erro_inesperado(RuntimeError("detalhe interno sigiloso"))
        self.assertEqual(codigo, 500)
        self.assertEqual(resposta.get_json(), {"erro": "Erro interno do servidor."})


class GunicornDeVerdade(unittest.TestCase):

    def test_01_sobe_com_a_configuracao_do_projeto(self):
        """Dado `gunicorn app:app` / Então /health responde 200 e o processo encerra limpo."""
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            porta = s.getsockname()[1]

        env = {**os.environ, "PORT": str(porta), "WEB_CONCURRENCY": "1", "GUNICORN_THREADS": "2"}
        processo = subprocess.Popen(
            [sys.executable, "-m", "gunicorn", "app:app", "--bind", f"127.0.0.1:{porta}"],
            cwd=RAIZ, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            corpo = None
            for _ in range(60):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{porta}/health", timeout=2) as r:
                        corpo = (r.status, json.loads(r.read()))
                        break
                except OSError:
                    time.sleep(0.25)
            self.assertEqual(corpo, (200, {"status": "ok"}))
        finally:
            processo.terminate()
            saida, _ = processo.communicate(timeout=30)

        self.assertIn("gthread", saida)
        self.assertNotIn("Traceback", saida)


if __name__ == "__main__":
    unittest.main(verbosity=2)
