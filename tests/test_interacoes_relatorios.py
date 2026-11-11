"""BDD: interações (RF02), responsável da oportunidade e relatórios por período.

Roda contra o banco do .env. Cria duas empresas de teste e remove tudo ao final.

    python3 -m unittest tests.test_interacoes_relatorios -v
"""
import unittest
import uuid

import bcrypt

import app as aplicacao
from database.conexao import get_db_connection


SENHA = "Senha@Teste123"
c = aplicacao.app.test_client()
ctx = {}


def sql(consulta, parametros=()):
    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(consulta, parametros)
            resultado = cursor.fetchone() if cursor.description else None
        conexao.commit()
    return resultado


def registrar(empresa, email):
    r = c.post("/auth/register", json={"nome_empresa": empresa, "nome_usuario": f"Gestor {empresa}",
                                       "email": email, "senha": SENHA})
    assert r.status_code == 201, r.get_json()
    ctx.setdefault("empresas", []).append(r.get_json()["empresa_id"])
    return r.get_json()


def login(email):
    r = c.post("/auth/login", json={"email": email, "senha": SENHA})
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def setUpModule():
    s = uuid.uuid4().hex[:8]
    a = registrar(f"Empresa A QA {s}", f"gestor.a.{s}@teste.local")
    b = registrar(f"Empresa B QA {s}", f"gestor.b.{s}@teste.local")
    ctx.update(empresa_a=a["empresa_id"], gestor_a=a["usuario_id"], empresa_b=b["empresa_id"])

    email_at = f"atend.a.{s}@teste.local"
    senha_hash = bcrypt.hashpw(SENHA.encode(), bcrypt.gensalt()).decode()
    ctx["atend_a"] = sql("""
        INSERT INTO usuarios (empresa_id, nome, email, senha, perfil)
        VALUES (%s, 'Atendente A', %s, %s, 'Atendimento') RETURNING id;
    """, (ctx["empresa_a"], email_at, senha_hash))[0]

    sessao_a = login(f"gestor.a.{s}@teste.local")
    ctx["login_a"] = sessao_a
    ctx["h_a"] = {"Authorization": f"Bearer {sessao_a['token']}"}
    ctx["h_b"] = {"Authorization": f"Bearer {login(f'gestor.b.{s}@teste.local')['token']}"}
    ctx["h_at"] = {"Authorization": f"Bearer {login(email_at)['token']}"}

    r = c.post("/clientes", headers=ctx["h_a"], json={"nome": "Cliente Interações"})
    ctx["cliente_a"] = r.get_json()["cliente_id"]
    r = c.post("/clientes", headers=ctx["h_a"], json={"nome": "Outro cliente"})
    ctx["cliente_a2"] = r.get_json()["cliente_id"]


def tearDownModule():
    for empresa_id in ctx.get("empresas", []):
        for tabela in ("interacoes", "tarefas", "oportunidades", "clientes",
                       "configuracoes", "usuarios"):
            sql(f"DELETE FROM {tabela} WHERE empresa_id = %s;", (empresa_id,))
        sql("DELETE FROM empresas WHERE id = %s;", (empresa_id,))


class Interacoes(unittest.TestCase):

    def test_01_registrar_e_listar_historico(self):
        """Dado um cliente / Quando registro Ligação e depois WhatsApp /
        Então o histórico vem do mais recente para o mais antigo, com autor."""
        for tipo in ("Ligação", "WhatsApp"):
            r = c.post("/interacoes", headers=ctx["h_at"], json={
                "cliente_id": ctx["cliente_a"], "tipo": tipo, "descricao": f"  Contato via {tipo}  "
            })
            self.assertEqual(r.status_code, 201, r.get_json())
            self.assertEqual(r.get_json()["interacao"]["descricao"], f"Contato via {tipo}")

        lista = c.get(f"/interacoes?cliente_id={ctx['cliente_a']}", headers=ctx["h_a"]).get_json()
        self.assertEqual([i["tipo"] for i in lista[:2]], ["WhatsApp", "Ligação"])
        self.assertEqual(lista[0]["usuario_nome"], "Atendente A")
        self.assertEqual(lista[0]["cliente_nome"], "Cliente Interações")

    def test_02_filtro_por_cliente_e_limite(self):
        """Dado interações em dois clientes / Então o filtro e o limite são respeitados."""
        c.post("/interacoes", headers=ctx["h_a"], json={
            "cliente_id": ctx["cliente_a2"], "tipo": "E-mail", "descricao": "Outro cliente"})

        lista = c.get(f"/interacoes?cliente_id={ctx['cliente_a2']}", headers=ctx["h_a"]).get_json()
        self.assertTrue(lista)
        self.assertTrue(all(i["cliente_id"] == ctx["cliente_a2"] for i in lista))

        self.assertEqual(len(c.get("/interacoes?limite=1", headers=ctx["h_a"]).get_json()), 1)
        for limite in (0, 201):
            self.assertEqual(c.get(f"/interacoes?limite={limite}", headers=ctx["h_a"]).status_code, 400)

    def test_03_validacoes(self):
        """Dado payloads inválidos / Então todos recebem 400."""
        invalidos = [
            {},
            {"cliente_id": ctx["cliente_a"], "tipo": "Telegrama", "descricao": "x"},
            {"cliente_id": ctx["cliente_a"], "tipo": "Ligação", "descricao": "   "},
            {"cliente_id": ctx["cliente_a"], "tipo": "Ligação"},
            {"cliente_id": "1", "tipo": "Ligação", "descricao": "x"},
            {"cliente_id": ctx["cliente_a"], "tipo": "Ligação", "descricao": "x" * 2001},
        ]
        for corpo in invalidos:
            with self.subTest(corpo=str(corpo)[:60]):
                self.assertEqual(c.post("/interacoes", headers=ctx["h_a"], json=corpo).status_code, 400)

    def test_04_isolamento_entre_empresas(self):
        """Dado a empresa B / Então não registra nem lê interações de clientes de A."""
        r = c.post("/interacoes", headers=ctx["h_b"], json={
            "cliente_id": ctx["cliente_a"], "tipo": "Ligação", "descricao": "invasão"})
        self.assertEqual(r.status_code, 404)

        lista = c.get(f"/interacoes?cliente_id={ctx['cliente_a']}", headers=ctx["h_b"]).get_json()
        self.assertEqual(lista, [])

    def test_05_oportunidade_precisa_ser_do_mesmo_cliente(self):
        """Dado uma oportunidade do cliente 2 / Quando vinculo à interação do cliente 1 /
        Então recebo 404."""
        op = c.post("/oportunidades", headers=ctx["h_a"], json={
            "cliente_id": ctx["cliente_a2"], "titulo": "Op do cliente 2"}).get_json()["oportunidade_id"]
        r = c.post("/interacoes", headers=ctx["h_a"], json={
            "cliente_id": ctx["cliente_a"], "oportunidade_id": op,
            "tipo": "Reunião", "descricao": "vínculo errado"})
        self.assertEqual(r.status_code, 404)

    def test_06_excluir_cliente_apaga_historico(self):
        """Dado um cliente com interações / Quando o Gestor o exclui /
        Então o histórico (dado pessoal) é removido junto (LGPD)."""
        cli = c.post("/clientes", headers=ctx["h_a"], json={"nome": "Temporário"}).get_json()["cliente_id"]
        c.post("/interacoes", headers=ctx["h_a"], json={
            "cliente_id": cli, "tipo": "Ligação", "descricao": "será apagada"})
        self.assertEqual(c.delete(f"/clientes/{cli}", headers=ctx["h_a"]).status_code, 200)
        self.assertEqual(sql("SELECT COUNT(*) FROM interacoes WHERE cliente_id = %s;", (cli,))[0], 0)


class ResponsavelEEmpresa(unittest.TestCase):

    def test_01_quem_cria_vira_responsavel(self):
        """Dado o Atendimento criando uma oportunidade / Então ele é o responsável."""
        op = c.post("/oportunidades", headers=ctx["h_at"], json={
            "cliente_id": ctx["cliente_a"], "titulo": "Op do atendente"}).get_json()["oportunidade_id"]
        dados = c.get(f"/oportunidades/{op}", headers=ctx["h_a"]).get_json()
        self.assertEqual(dados["responsavel_id"], ctx["atend_a"])
        self.assertEqual(dados["responsavel_nome"], "Atendente A")
        self.assertIsNotNone(dados["criado_em"])
        self.assertIsNotNone(dados["etapa_atualizada_em"])

    def test_02_login_informa_nome_da_empresa(self):
        """Então o login traz o nome da empresa ativa para o Header."""
        self.assertTrue(ctx["login_a"]["usuario"]["empresa_nome"].startswith("Empresa A QA"))


class RelatoriosPorPeriodo(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        def criar(valor, etapa):
            return c.post("/oportunidades", headers=ctx["h_a"], json={
                "cliente_id": ctx["cliente_a"], "titulo": f"R{valor}", "valor": valor,
                "etapa": etapa}).get_json()["oportunidade_id"]

        cls.venda_hoje = criar(1000, "Fechado")
        cls.venda_antiga = criar(5000, "Fechado")
        # Fechada e criada há 400 dias: fora de Mês/Trimestre/Ano, dentro de "total"
        sql("""UPDATE oportunidades SET criado_em = NOW() - INTERVAL '400 days',
                                        etapa_atualizada_em = NOW() - INTERVAL '400 days'
               WHERE id = %s;""", (cls.venda_antiga,))

    def relatorio(self, periodo=None, headers=None):
        url = "/relatorios/vendas" + (f"?periodo={periodo}" if periodo else "")
        return c.get(url, headers=headers or ctx["h_a"])

    def test_01_periodo_filtra_receita_pela_data_de_fechamento(self):
        """Dado uma venda de hoje e uma de 400 dias atrás /
        Então 'mes' soma só a de hoje e 'total' soma as duas."""
        mes = self.relatorio("mes").get_json()
        total = self.relatorio().get_json()

        self.assertIn(self.venda_hoje, [v["id"] for v in mes["vendas"]])
        self.assertNotIn(self.venda_antiga, [v["id"] for v in mes["vendas"]])
        self.assertEqual(total["receita_total"] - mes["receita_total"], 5000.0)
        self.assertIsNotNone(mes["inicio_periodo"])
        self.assertIsNone(total["inicio_periodo"])

    def test_02_conversao_por_coorte_nunca_passa_de_100(self):
        """Então a taxa de conversão de qualquer período fica entre 0 e 100%."""
        for periodo in ("mes", "trimestre", "ano", "total"):
            with self.subTest(periodo=periodo):
                taxa = self.relatorio(periodo).get_json()["taxa_conversao"]
                self.assertGreaterEqual(taxa, 0)
                self.assertLessEqual(taxa, 100)

    def test_03_funil_na_ordem_das_etapas_e_com_zeros(self):
        """Então o funil traz as 5 etapas, na ordem do Kanban, mesmo vazias."""
        funil = self.relatorio().get_json()["funil"]
        self.assertEqual([f["etapa"] for f in funil],
                         ["Prospecção", "Qualificação", "Proposta", "Negociação", "Fechado"])

    def test_04_serie_mensal_de_12_meses(self):
        """Então a série tem 12 meses e o mês atual inclui a venda de hoje."""
        serie = self.relatorio().get_json()["serie_mensal"]
        self.assertEqual(len(serie), 12)
        self.assertGreaterEqual(serie[-1]["receita"], 1000.0)

    def test_05_canais_trazem_os_quatro_tipos(self):
        """Então 'canais' traz Ligação, WhatsApp, E-mail e Reunião com contagens."""
        canais = {x["canal"]: x for x in self.relatorio("ano").get_json()["canais"]}
        self.assertEqual(set(canais), {"Ligação", "WhatsApp", "E-mail", "Reunião"})
        self.assertGreaterEqual(canais["Ligação"]["interacoes"], 0)

    def test_06_periodo_invalido_e_rbac(self):
        """Dado período inválido / Então 400; Atendimento / Então 403."""
        self.assertEqual(self.relatorio("semana").status_code, 400)
        self.assertEqual(self.relatorio("mes", ctx["h_at"]).status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
