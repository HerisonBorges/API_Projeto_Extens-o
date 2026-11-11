"""Cenários de aceite do QA, executados contra o banco configurado no .env.

Uso (na raiz do projeto, depois de aplicar as migrações):
    python3 -m unittest tests.aceite_qa -v

Cria duas empresas de teste (A e B) com e-mails únicos e remove todos os
dados criados ao final, mesmo se algum cenário falhar.
"""
import unittest
import uuid
from datetime import date, timedelta

import bcrypt

import app as aplicacao
from database.conexao import conectar_banco


SENHA = "Senha@Teste123"


def executar_sql(sql, parametros=()):
    conexao = conectar_banco()
    try:
        with conexao.cursor() as cursor:
            cursor.execute(sql, parametros)
            resultado = cursor.fetchone() if cursor.description else None
        conexao.commit()
        return resultado
    finally:
        conexao.close()


class CenariosAceite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.c = aplicacao.app.test_client()
        cls.empresas = []
        sufixo = uuid.uuid4().hex[:8]

        cls.email_gestor_a = f"gestor.a.{sufixo}@teste.local"
        cls.email_gestor_b = f"gestor.b.{sufixo}@teste.local"
        cls.email_atend_a = f"atend.a.{sufixo}@teste.local"

        cls.empresa_a = cls._registrar("Empresa A QA", "Gestor A", cls.email_gestor_a)
        cls.empresa_b = cls._registrar("Empresa B QA", "Gestor B", cls.email_gestor_b)

        # /auth/register só cria Gestor; o Atendimento é inserido direto no banco
        senha_hash = bcrypt.hashpw(SENHA.encode(), bcrypt.gensalt()).decode()
        executar_sql("""
            INSERT INTO usuarios (empresa_id, nome, email, senha, perfil)
            VALUES (%s, %s, %s, %s, 'Atendimento');
        """, (cls.empresa_a, "Atendente A", cls.email_atend_a, senha_hash))

        cls.h_gestor_a = cls._login(cls.email_gestor_a, "Gestor")
        cls.h_gestor_b = cls._login(cls.email_gestor_b, "Gestor")
        cls.h_atend_a = cls._login(cls.email_atend_a, "Atendimento")

    @classmethod
    def tearDownClass(cls):
        for empresa_id in cls.empresas:
            for tabela in ("tarefas", "oportunidades", "clientes",
                           "configuracoes", "usuarios"):
                executar_sql(f"DELETE FROM {tabela} WHERE empresa_id = %s;",
                             (empresa_id,))
            executar_sql("DELETE FROM empresas WHERE id = %s;", (empresa_id,))

    @classmethod
    def _registrar(cls, empresa, usuario, email):
        r = cls.c.post("/auth/register", json={
            "nome_empresa": empresa, "nome_usuario": usuario,
            "email": email, "senha": SENHA
        })
        assert r.status_code == 201, f"register falhou: {r.status_code} {r.get_json()}"
        empresa_id = r.get_json()["empresa_id"]
        cls.empresas.append(empresa_id)
        return empresa_id

    @classmethod
    def _login(cls, email, perfil_esperado):
        r = cls.c.post("/auth/login", json={"email": email, "senha": SENHA})
        assert r.status_code == 200, f"login falhou: {r.status_code} {r.get_json()}"
        corpo = r.get_json()
        assert corpo["usuario"]["perfil"] == perfil_esperado, corpo
        return {"Authorization": f"Bearer {corpo['token']}"}

    # ------------------------------------------------------------------
    def test_1_cadastro_cliente_com_isolamento(self):
        """Cenário 1: cadastrar cliente e garantir isolamento entre empresas."""
        r = self.c.post("/clientes", headers=self.h_atend_a, json={
            "nome": "Maria", "email": "maria@exemplo.com"
        })
        self.assertEqual(r.status_code, 201, r.get_json())
        cliente_id = r.get_json()["cliente_id"]
        type(self).cliente_id = cliente_id

        ids_a = [c["id"] for c in self.c.get("/clientes", headers=self.h_gestor_a).get_json()]
        self.assertIn(cliente_id, ids_a)

        ids_b = [c["id"] for c in self.c.get("/clientes", headers=self.h_gestor_b).get_json()]
        self.assertNotIn(cliente_id, ids_b)

        self.assertEqual(
            self.c.get(f"/clientes/{cliente_id}", headers=self.h_gestor_b).status_code, 404)
        self.assertEqual(
            self.c.delete(f"/clientes/{cliente_id}", headers=self.h_atend_a).status_code, 403)

        # empresa_id enviado no corpo é ignorado: o cliente fica na empresa do token
        r = self.c.post("/clientes", headers=self.h_gestor_b, json={
            "nome": "Intruso", "empresa_id": self.empresa_a
        })
        intruso = r.get_json()["cliente_id"]
        ids_a = [c["id"] for c in self.c.get("/clientes", headers=self.h_gestor_a).get_json()]
        self.assertNotIn(intruso, ids_a)

    def test_2_follow_up_e_mover_funil(self):
        """Cenário 2: registrar follow-up vinculado e mover oportunidade."""
        r = self.c.post("/oportunidades", headers=self.h_atend_a, json={
            "cliente_id": self.cliente_id, "titulo": "Orçamento Maria",
            "valor": 500, "etapa": "Prospecção"
        })
        self.assertEqual(r.status_code, 201, r.get_json())
        op_id = r.get_json()["oportunidade_id"]
        type(self).oportunidade_id = op_id

        antes = executar_sql(
            "SELECT etapa_atualizada_em FROM oportunidades WHERE id = %s;", (op_id,))[0]

        amanha = (date.today() + timedelta(days=1)).isoformat()
        r = self.c.post("/tarefas", headers=self.h_atend_a, json={
            "titulo": "Ligar para cliente", "cliente_id": self.cliente_id,
            "oportunidade_id": op_id, "data_vencimento": amanha
        })
        self.assertEqual(r.status_code, 201, r.get_json())

        r = self.c.patch(f"/oportunidades/{op_id}/etapa", headers=self.h_atend_a,
                         json={"etapa": "Proposta"})
        self.assertEqual(r.status_code, 200, r.get_json())

        etapa, depois = executar_sql(
            "SELECT etapa, etapa_atualizada_em FROM oportunidades WHERE id = %s;", (op_id,))
        self.assertEqual(etapa, "Proposta")
        self.assertGreater(depois, antes)

        # Empresa B não consegue mexer nem se vincular à oportunidade de A
        self.assertEqual(self.c.patch(f"/oportunidades/{op_id}/etapa", headers=self.h_gestor_b,
                                      json={"etapa": "Fechado"}).status_code, 404)
        self.assertEqual(self.c.post("/tarefas", headers=self.h_gestor_b, json={
            "titulo": "x", "oportunidade_id": op_id}).status_code, 404)
        self.assertEqual(self.c.patch(f"/oportunidades/{op_id}/etapa", headers=self.h_atend_a,
                                      json={"etapa": "Ganhou"}).status_code, 400)

    def test_3_kpis_dashboard_e_alerta_rf04(self):
        """Cenário 3: 2 fechadas + 1 em Proposta há 8 dias corridos."""
        for valor in (1000, 3000):
            r = self.c.post("/oportunidades", headers=self.h_gestor_a, json={
                "cliente_id": self.cliente_id, "titulo": f"Venda {valor}",
                "valor": valor, "etapa": "Fechado"
            })
            self.assertEqual(r.status_code, 201, r.get_json())

        executar_sql("""
            UPDATE oportunidades
            SET etapa_atualizada_em = NOW() - INTERVAL '8 days'
            WHERE id = %s;
        """, (self.oportunidade_id,))

        r = self.c.get("/relatorios/vendas", headers=self.h_gestor_a)
        self.assertEqual(r.status_code, 200, r.get_json())
        kpi = r.get_json()
        self.assertEqual(kpi["vendas_fechadas"], 2)
        self.assertEqual(kpi["receita_total"], 4000.0)
        self.assertEqual(kpi["ticket_medio"], 2000.0)
        self.assertEqual(kpi["taxa_conversao"], 66.67)

        self.assertEqual(
            self.c.get("/relatorios/vendas", headers=self.h_atend_a).status_code, 403)

        r = self.c.get(f"/dashboard/{self.empresa_a}", headers=self.h_gestor_a)
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["total_oportunidades"], 3)
        self.assertEqual(r.get_json()["receita_total"], 4000.0)
        self.assertEqual(
            self.c.get(f"/dashboard/{self.empresa_a}", headers=self.h_gestor_b).status_code, 403)

        # RF04 com o padrão de 7 dias corridos: 8 dias parado gera alerta
        alertas = self.c.get("/tarefas/alertas", headers=self.h_atend_a).get_json()
        self.assertEqual(alertas["dias_alerta_orcamento"], 7)
        parados = {o["id"]: o for o in alertas["orcamentos_parados"]}
        self.assertIn(self.oportunidade_id, parados)
        self.assertEqual(parados[self.oportunidade_id]["dias_parado"], 8)

        # Gestor sobe X para 10: o alerta some (configuração sem deploy)
        r = self.c.put("/configuracoes", headers=self.h_gestor_a,
                       json={"dias_alerta_orcamento": 10})
        self.assertEqual(r.status_code, 200, r.get_json())
        alertas = self.c.get("/tarefas/alertas", headers=self.h_atend_a).get_json()
        self.assertNotIn(self.oportunidade_id,
                         [o["id"] for o in alertas["orcamentos_parados"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
