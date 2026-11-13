"""BDD: lacunas de processo apontadas na análise de produto.

    python3 -m unittest tests.test_lacunas_processo -v

Roda contra o banco do .env. Cria duas empresas de teste e remove tudo ao final.
"""
import unittest
import uuid
from datetime import date, timedelta

import app as aplicacao
from database.conexao import get_db_connection

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


def registrar(nome):
    email = f"gestor.{uuid.uuid4().hex[:10]}@teste.local"
    r = c.post("/auth/register", json={"nome_empresa": nome, "nome_usuario": f"Gestor {nome}",
                                       "email": email, "senha": SENHA})
    assert r.status_code == 201, r.get_json()
    ctx.setdefault("empresas", []).append(r.get_json()["empresa_id"])
    token = c.post("/auth/login", json={"email": email, "senha": SENHA}).get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def setUpModule():
    ctx["h_a"] = registrar(f"Empresa A Lacunas {uuid.uuid4().hex[:6]}")
    ctx["h_b"] = registrar(f"Empresa B Lacunas {uuid.uuid4().hex[:6]}")
    ctx["cliente"] = c.post("/clientes", headers=ctx["h_a"], json={"nome": "Cliente Lacunas"}).get_json()["cliente_id"]


def tearDownModule():
    for empresa_id in ctx.get("empresas", []):
        for tabela in ("auditoria_usuarios", "interacoes", "tarefas", "oportunidades",
                       "clientes", "configuracoes", "usuarios"):
            sql(f"DELETE FROM {tabela} WHERE empresa_id = %s;", (empresa_id,))
        sql("DELETE FROM empresas WHERE id = %s;", (empresa_id,))


class CriarFollowup(unittest.TestCase):
    """Item 1: criar follow-up pela tela."""

    def test_01_cria_follow_up_completo(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()
        r = c.post("/tarefas", headers=ctx["h_a"], json={
            "titulo": "  Ligar para confirmar orçamento  ", "descricao": "Pedir prazo",
            "data_vencimento": amanha, "cliente_id": ctx["cliente"]})
        self.assertEqual(r.status_code, 201, r.get_json())

        tarefa = next(t for t in c.get("/tarefas?concluida=false", headers=ctx["h_a"]).get_json()
                      if t["id"] == r.get_json()["tarefa_id"])
        self.assertEqual(tarefa["titulo"], "Ligar para confirmar orçamento")
        self.assertEqual(tarefa["data_vencimento"], amanha)
        self.assertEqual(tarefa["cliente_id"], ctx["cliente"])

    def test_02_entradas_invalidas_dao_400_e_nao_500(self):
        """Antes, data ou título inválidos chegavam ao banco e viravam erro 500."""
        invalidos = [
            {"titulo": "x", "data_vencimento": "2026-13-45"},
            {"titulo": "x", "data_vencimento": "amanhã"},
            {"titulo": "x", "data_vencimento": 12345},
            {"titulo": "x" * 151},
            {"titulo": "   "},
            {"titulo": "x", "descricao": "y" * 2001},
            {"titulo": "x", "cliente_id": "1"},
            {"titulo": "x", "cliente_id": True},
        ]
        for corpo in invalidos:
            with self.subTest(corpo=str(corpo)[:60]):
                r = c.post("/tarefas", headers=ctx["h_a"], json=corpo)
                self.assertEqual(r.status_code, 400, r.get_json())

    def test_03_edicao_usa_as_mesmas_regras(self):
        tid = c.post("/tarefas", headers=ctx["h_a"], json={"titulo": "Editar"}).get_json()["tarefa_id"]
        r = c.put(f"/tarefas/{tid}", headers=ctx["h_a"], json={"titulo": "Editar", "data_vencimento": "31/12/2026"})
        self.assertEqual(r.status_code, 400)

    def test_04_nao_vincula_cliente_de_outra_empresa(self):
        r = c.post("/tarefas", headers=ctx["h_b"], json={"titulo": "Invasão", "cliente_id": ctx["cliente"]})
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
