"""BDD: fuso horário nas contas de data, limite de tamanho de requisição e
travas do seed.

    python3 -m unittest tests.test_fuso_e_limites -v

Roda contra o banco do .env. Cria uma empresa de teste e remove tudo ao final.
"""
import os
import subprocess
import sys
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import app as aplicacao
import seguranca
from database.conexao import get_db_connection

RAIZ = Path(__file__).resolve().parent.parent
SENHA = "Gestor#Teste2026"
c = aplicacao.app.test_client()
ctx = {}


def sql(consulta, parametros=()):
    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(consulta, parametros)
            resultado = cursor.fetchall() if cursor.description else None
        conexao.commit()
    return resultado


def setUpModule():
    email = f"gestor.{uuid.uuid4().hex[:10]}@teste.local"
    r = c.post("/auth/register", json={"nome_empresa": f"Empresa Fuso QA {uuid.uuid4().hex[:6]}",
                                       "nome_usuario": "Gestor Fuso", "email": email, "senha": SENHA})
    assert r.status_code == 201, r.get_json()
    ctx["empresa"] = r.get_json()["empresa_id"]
    token = c.post("/auth/login", json={"email": email, "senha": SENHA}).get_json()["token"]
    ctx["h"] = {"Authorization": f"Bearer {token}"}
    ctx["cliente"] = c.post("/clientes", headers=ctx["h"], json={"nome": "Cliente Fuso"}).get_json()["cliente_id"]


def tearDownModule():
    if "empresa" in ctx:
        for tabela in ("auditoria_usuarios", "interacoes", "tarefas", "oportunidades",
                       "clientes", "configuracoes", "usuarios"):
            sql(f"DELETE FROM {tabela} WHERE empresa_id = %s;", (ctx["empresa"],))
        sql("DELETE FROM empresas WHERE id = %s;", (ctx["empresa"],))


def fuso_com_outra_data():
    """Um fuso em que, AGORA, a data local é diferente da data em UTC.

    Reproduz em qualquer horário o caso real das 21h-24h em São Paulo."""
    hora_utc = datetime.now(timezone.utc).hour
    return "Etc/GMT+12" if hora_utc < 12 else "Etc/GMT-14"  # UTC-12 ou UTC+14


class FusoNosAlertas(unittest.TestCase):

    def test_01_vencido_usa_o_hoje_da_empresa(self):
        """Dado um fuso em que a data local difere da data UTC /
        Então um follow-up de 'hoje local' não está vencido e o de 'ontem local' está."""
        fuso = fuso_com_outra_data()
        hoje, ontem = sql("""SELECT (NOW() AT TIME ZONE %s)::date,
                                    (NOW() AT TIME ZONE %s)::date - 1;""", (fuso, fuso))[0]
        self.assertNotEqual(hoje, sql("SELECT CURRENT_DATE;")[0][0], "pré-condição: datas diferentes")

        ids = {}
        for nome, data in (("hoje", hoje), ("ontem", ontem)):
            r = c.post("/tarefas", headers=ctx["h"], json={
                "titulo": f"Follow-up {nome}", "cliente_id": ctx["cliente"],
                "data_vencimento": data.isoformat()})
            self.assertEqual(r.status_code, 201, r.get_json())
            ids[nome] = r.get_json()["tarefa_id"]

        with mock.patch.object(seguranca, "TZ_EMPRESA", fuso):
            vencidas = [t["id"] for t in c.get("/tarefas/alertas", headers=ctx["h"]).get_json()["tarefas_vencidas"]]

        self.assertNotIn(ids["hoje"], vencidas)
        self.assertIn(ids["ontem"], vencidas)

    def test_02_dias_parado_conta_dias_no_fuso_da_empresa(self):
        """Dado uma proposta parada há exatamente 10 dias locais / Então dias_parado = 10."""
        fuso = fuso_com_outra_data()
        op = c.post("/oportunidades", headers=ctx["h"], json={
            "cliente_id": ctx["cliente"], "titulo": "Proposta parada", "etapa": "Proposta"}).get_json()["oportunidade_id"]
        sql("UPDATE oportunidades SET etapa_atualizada_em = NOW() - INTERVAL '10 days' WHERE id = %s;", (op,))

        with mock.patch.object(seguranca, "TZ_EMPRESA", fuso):
            parados = {o["id"]: o for o in c.get("/tarefas/alertas", headers=ctx["h"]).get_json()["orcamentos_parados"]}
        self.assertEqual(parados[op]["dias_parado"], 10)


class FusoNosRelatorios(unittest.TestCase):

    def test_01_venda_na_ultima_hora_do_mes_fica_no_mes_certo(self):
        """Dado uma venda fechada 1h antes da virada do mês, no horário da empresa /
        Então ela conta no mês anterior, e não no mês atual (antes ia +3h para frente)."""
        op = c.post("/oportunidades", headers=ctx["h"], json={
            "cliente_id": ctx["cliente"], "titulo": "Venda virada de mês", "valor": 777.77,
            "etapa": "Fechado"}).get_json()["oportunidade_id"]
        sql("""UPDATE oportunidades
               SET etapa_atualizada_em =
                   date_trunc('month', NOW() AT TIME ZONE %(tz)s) AT TIME ZONE %(tz)s - INTERVAL '1 hour'
               WHERE id = %(id)s;""", {"tz": seguranca.TZ_EMPRESA, "id": op})

        r = c.get("/relatorios/vendas", headers=ctx["h"]).get_json()
        anterior, atual = r["serie_mensal"][-2], r["serie_mensal"][-1]
        self.assertAlmostEqual(anterior["receita"], 777.77, places=2)
        self.assertEqual(atual["receita"], 0.0)

        mes = c.get("/relatorios/vendas?periodo=mes", headers=ctx["h"]).get_json()
        self.assertNotIn(op, [v["id"] for v in mes["vendas"]])

    def test_02_api_devolve_datas_com_fuso(self):
        """Então os horários saem com o fuso (o navegador não lê como hora local)."""
        ops = c.get("/oportunidades", headers=ctx["h"]).get_json()
        self.assertTrue(ops)
        for campo in ("criado_em", "etapa_atualizada_em"):
            with self.subTest(campo=campo):
                self.assertRegex(ops[0][campo], r"[+-]\d{2}:\d{2}$")


class LimiteDeTamanho(unittest.TestCase):

    def test_01_corpo_acima_de_1mb_recebe_413_em_portugues(self):
        corpo = '{"email":"a@b.co","senha":"' + "x" * (1024 * 1024 + 10) + '"}'
        r = c.post("/auth/login", data=corpo, content_type="application/json")
        self.assertEqual(r.status_code, 413)
        self.assertEqual(r.get_json(), {"erro": "Requisição grande demais."})

    def test_02_corpo_normal_continua_funcionando(self):
        r = c.post("/auth/login", json={"email": "ninguem@exemplo.com", "senha": "Qualquer#123"})
        self.assertEqual(r.status_code, 401)


class TravasDoSeed(unittest.TestCase):

    def rodar(self, *args, env_extra=None):
        return subprocess.run([sys.executable, "-m", "database.seed_fenix", *args], cwd=RAIZ,
                              env={**os.environ, **(env_extra or {})},
                              capture_output=True, text=True, timeout=120)

    def contagem_fenix(self):
        return sql("""SELECT COUNT(*) FROM clientes c JOIN empresas e ON e.id = c.empresa_id
                      WHERE e.nome = 'Loja Fênix';""")[0][0]

    def test_01_recusa_em_producao(self):
        antes = self.contagem_fenix()
        r = self.rodar("--resetar", "--sim", env_extra={"APP_ENV": "producao"})
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("Recusado", r.stdout)
        self.assertEqual(self.contagem_fenix(), antes)

    def test_02_resetar_sem_confirmacao_nao_apaga(self):
        antes = self.contagem_fenix()
        r = self.rodar("--resetar")
        if antes == 0:
            self.skipTest("Loja Fênix não existe neste banco")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("vai APAGAR", r.stdout)
        self.assertIn("--sim", r.stdout)
        self.assertEqual(self.contagem_fenix(), antes)


if __name__ == "__main__":
    unittest.main(verbosity=2)
