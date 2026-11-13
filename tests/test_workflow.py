"""BDD: workflow do worker de reciclagem (.github/workflows/worker_reciclagem.yml).

    python3 -m unittest tests.test_workflow -v

Valida a estrutura de segurança do YAML e executa o script do passo
"Executar o worker" no bash, com as mesmas flags do GitHub (-eo pipefail),
contra o banco do .env em modo simulação.
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")
ARQUIVO = RAIZ / ".github" / "workflows" / "worker_reciclagem.yml"


def carregar():
    dados = yaml.safe_load(ARQUIVO.read_text(encoding="utf-8"))
    # PyYAML (YAML 1.1) lê a chave "on" como booleano True
    dados["on"] = dados.pop(True, dados.get("on"))
    return dados


class EstruturaDoWorkflow(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.wf = carregar()
        cls.job = cls.wf["jobs"]["reciclar"]
        cls.passos = {p["name"]: p for p in cls.job["steps"]}

    def test_01_roda_de_hora_em_hora_e_manualmente(self):
        """Então há um cron horário e o disparo manual com simulação ligada por padrão."""
        crons = [s["cron"] for s in self.wf["on"]["schedule"]]
        self.assertEqual(len(crons), 1)
        minuto, hora, *_ = crons[0].split()
        self.assertTrue(minuto.isdigit() and 0 <= int(minuto) <= 59)
        self.assertEqual(hora, "*")

        entradas = self.wf["on"]["workflow_dispatch"]["inputs"]
        self.assertIs(entradas["simulacao"]["default"], True)
        self.assertIn("empresa", entradas)

    def test_02_privilegio_minimo_e_sem_execucao_dupla(self):
        self.assertEqual(self.wf["permissions"], {"contents": "read"})
        self.assertEqual(self.wf["concurrency"]["group"], "worker-reciclagem")
        self.assertIs(self.wf["concurrency"]["cancel-in-progress"], False)
        self.assertLessEqual(self.job["timeout-minutes"], 15)
        self.assertEqual(self.job["environment"], "producao")

    def test_03_actions_fixadas_por_sha(self):
        """Então toda action externa usa SHA completo de commit, não tag móvel."""
        usos = [p["uses"] for p in self.job["steps"] if "uses" in p]
        self.assertTrue(usos)
        for uso in usos:
            with self.subTest(uso=uso):
                self.assertRegex(uso, r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")

    def test_04_checkout_nao_guarda_token(self):
        checkout = next(p for p in self.job["steps"] if p.get("uses", "").startswith("actions/checkout@"))
        self.assertIs(checkout["with"]["persist-credentials"], False)

    def test_05_secrets_e_entradas_nunca_interpolados_em_scripts(self):
        """Então nenhum 'run' contém ${{ ... }}: secrets e entradas chegam só por env."""
        for passo in self.job["steps"]:
            if "run" in passo:
                with self.subTest(passo=passo["name"]):
                    self.assertNotIn("${{", passo["run"])

    def test_06_somente_credenciais_do_banco(self):
        """Então o job recebe só os 5 secrets do banco; SECRET_KEY não é exposta."""
        referenciados = set(re.findall(r"secrets\.(\w+)", ARQUIVO.read_text(encoding="utf-8")))
        self.assertEqual(referenciados, {"DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"})
        self.assertNotIn("SECRET_KEY", self.job["env"])
        self.assertEqual(self.job["env"]["PGSSLMODE"], "require")

    def test_07_versao_do_python_vem_do_projeto(self):
        setup = next(p for p in self.job["steps"] if p.get("uses", "").startswith("actions/setup-python@"))
        arquivo = setup["with"]["python-version-file"]
        self.assertTrue((RAIZ / arquivo).is_file())
        self.assertRegex((RAIZ / arquivo).read_text().strip(), r"^3\.\d+$")


class ScriptDeExecucao(unittest.TestCase):
    """Roda o script real do passo, como o GitHub roda (bash -eo pipefail)."""

    @classmethod
    def setUpClass(cls):
        cls.script = {p["name"]: p for p in carregar()["jobs"]["reciclar"]["steps"]}["Executar o worker"]["run"]
        # No runner, o setup-python expõe "python"; aqui pode existir só "python3"
        cls.atalhos = tempfile.TemporaryDirectory()
        os.symlink(sys.executable, Path(cls.atalhos.name) / "python")

    @classmethod
    def tearDownClass(cls):
        cls.atalhos.cleanup()

    def executar(self, simulacao, empresa):
        env = {**os.environ, "ENTRADA_SIMULACAO": simulacao, "ENTRADA_EMPRESA": empresa,
               "GITHUB_STEP_SUMMARY": os.devnull,
               "PATH": f"{self.atalhos.name}{os.pathsep}{os.environ['PATH']}"}
        return subprocess.run(["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", self.script],
                              cwd=RAIZ, env=env, capture_output=True, text=True, timeout=120)

    def test_01_simulacao_por_empresa(self):
        r = self.executar("true", "12")
        self.assertEqual(r.returncode, 0, r.stderr[-500:])
        self.assertIn("[dry-run]", r.stdout)
        self.assertIn("(empresa 12)", r.stdout)

    def test_02_simulacao_sem_empresa_cobre_todas(self):
        r = self.executar("true", "")
        self.assertEqual(r.returncode, 0, r.stderr[-500:])
        self.assertIn("(todas as empresas)", r.stdout)

    def test_03_injecao_na_entrada_empresa_e_recusada(self):
        """Dado uma entrada maliciosa / Então o script para antes de rodar qualquer coisa."""
        for malicioso in ("12; touch /tmp/pwned_sandro", "$(touch /tmp/pwned_sandro)", "-1", "1 2"):
            with self.subTest(entrada=malicioso):
                r = self.executar("true", malicioso)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn("empresa deve ser um número inteiro", r.stdout)
        self.assertFalse(Path("/tmp/pwned_sandro").exists())

    def test_04_saida_nao_expoe_titulos(self):
        """Dado agendamentos vencidos / Então o log mostra só IDs e datas (repo público)."""
        from database.conexao import get_db_connection
        with get_db_connection() as c, c.cursor() as cur:
            cur.execute("SELECT titulo FROM oportunidades WHERE empresa_id = 12;")
            titulos = [t for (t,) in cur.fetchall()]
        r = self.executar("true", "12")
        for titulo in titulos:
            self.assertNotIn(titulo, r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
