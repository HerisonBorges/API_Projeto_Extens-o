"""BDD: o front recebe quanto falta para a janela de acesso acabar, para
encerrar a sessão sozinho no fim do expediente.

    python3 -m unittest tests.test_janela_sessao -v

Roda contra o banco do .env. Cria uma empresa de teste e remove tudo ao final.
"""
import unittest
import uuid
from datetime import datetime, timedelta

import app as aplicacao
from database.conexao import get_db_connection
from seguranca import SQL_SEGUNDOS_ATE_FIM_JANELA, TZ_EMPRESA

SENHA = "Gestor#Janela2026"
c = aplicacao.app.test_client()
ctx = {}


def sql(consulta, parametros=()):
    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(consulta, parametros)
            resultado = cursor.fetchall() if cursor.description else None
        conexao.commit()
    return resultado


def agora_na_empresa():
    """Hora local da empresa pelo relógio do banco (o mesmo que a API usa)."""
    return sql("SELECT (NOW() AT TIME ZONE %s)::time;", (TZ_EMPRESA,))[0][0]


def deslocar(hora, minutos):
    base = datetime(2000, 1, 1, hora.hour, hora.minute, hora.second)
    return (base + timedelta(minutes=minutos)).time()


def segundos_esperados(agora, fim):
    a = agora.hour * 3600 + agora.minute * 60 + agora.second + agora.microsecond / 1e6
    f = fim.hour * 3600 + fim.minute * 60 + fim.second
    return (f - a) % 86400


def setUpModule():
    ctx["email"] = f"gestor.{uuid.uuid4().hex[:10]}@teste.local"
    r = c.post("/auth/register", json={"nome_empresa": f"Empresa Janela QA {uuid.uuid4().hex[:6]}",
                                       "nome_usuario": "Gestor Janela", "email": ctx["email"], "senha": SENHA})
    assert r.status_code == 201, r.get_json()
    ctx["empresa"] = r.get_json()["empresa_id"]
    ctx["usuario"] = r.get_json()["usuario_id"]


def tearDownModule():
    if "empresa" in ctx:
        for tabela in ("auditoria_usuarios", "usuarios"):
            sql(f"DELETE FROM {tabela} WHERE empresa_id = %s;", (ctx["empresa"],))
        sql("DELETE FROM empresas WHERE id = %s;", (ctx["empresa"],))


def definir_janela(inicio, fim):
    sql("UPDATE usuarios SET hora_inicio_acesso = %s, hora_fim_acesso = %s WHERE id = %s;",
        (inicio, fim, ctx["usuario"]))


def entrar():
    return c.post("/auth/login", json={"email": ctx["email"], "senha": SENHA})


class FormulaNoBanco(unittest.TestCase):
    """Dado o relógio do banco, a expressão conta os segundos até o fim da janela."""

    def calcular(self, inicio, fim):
        linha = sql(f"""
            SELECT (NOW() AT TIME ZONE %(tz)s)::time, {SQL_SEGUNDOS_ATE_FIM_JANELA}
            FROM (SELECT %(inicio)s::time AS hora_inicio_acesso, %(fim)s::time AS hora_fim_acesso) j;
        """, {"tz": TZ_EMPRESA, "inicio": inicio, "fim": fim})[0]
        return linha

    def test_01_fim_mais_tarde_no_mesmo_dia(self):
        agora = agora_na_empresa()
        fim = deslocar(agora, 30)
        hora_banco, segundos = self.calcular(deslocar(agora, -60), fim)
        self.assertAlmostEqual(segundos, segundos_esperados(hora_banco, fim), delta=1)

    def test_02_fim_ja_passou_hoje_conta_ate_amanha(self):
        """Janela que cruza a meia-noite (ex.: 22:00-02:00): o fim é no dia seguinte."""
        agora = agora_na_empresa()
        fim = deslocar(agora, -10)
        hora_banco, segundos = self.calcular(deslocar(agora, -20), fim)
        self.assertAlmostEqual(segundos, segundos_esperados(hora_banco, fim), delta=1)
        self.assertGreater(segundos, 23 * 3600)

    def test_03_sem_restricao_devolve_nulo(self):
        self.assertIsNone(self.calcular(None, None)[1])


class RespostaDaApi(unittest.TestCase):

    def tearDown(self):
        definir_janela(None, None)

    def test_01_acesso_irrestrito_nao_agenda_fim(self):
        definir_janela(None, None)
        r = entrar()
        self.assertEqual(r.status_code, 200, r.get_json())
        usuario = r.get_json()["usuario"]
        self.assertIsNone(usuario["segundos_ate_fim_janela"])
        self.assertEqual(usuario["fuso_horario"], TZ_EMPRESA)

    def test_02_login_e_me_devolvem_o_tempo_restante(self):
        agora = agora_na_empresa()
        definir_janela(deslocar(agora, -60), deslocar(agora, 20))
        r = entrar()
        self.assertEqual(r.status_code, 200, r.get_json())
        segundos = r.get_json()["usuario"]["segundos_ate_fim_janela"]
        self.assertTrue(18 * 60 <= segundos <= 20 * 60, segundos)

        h = {"Authorization": f"Bearer {r.get_json()['token']}"}
        me = c.get("/auth/me", headers=h)
        self.assertEqual(me.status_code, 200)
        self.assertTrue(18 * 60 <= me.get_json()["segundos_ate_fim_janela"] <= 20 * 60)

    def test_03_fora_da_janela_me_encerra_a_sessao(self):
        """O front revalida em /auth/me ao voltar para a aba: fora do horário, 403."""
        definir_janela(None, None)
        token = entrar().get_json()["token"]
        agora = agora_na_empresa()
        definir_janela(deslocar(agora, 30), deslocar(agora, 90))
        r = c.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["error"], "HORARIO_BLOQUEADO")


if __name__ == "__main__":
    unittest.main()
