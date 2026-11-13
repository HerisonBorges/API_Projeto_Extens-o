"""BDD: cadastro e edição de clientes.

    python3 -m unittest tests.test_clientes_edicao -v

Roda contra o banco do .env. Cria duas empresas de teste e remove tudo ao final.
"""
import unittest
import uuid

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
    ctx["h_a"] = registrar(f"Empresa A Clientes {uuid.uuid4().hex[:6]}")
    ctx["h_b"] = registrar(f"Empresa B Clientes {uuid.uuid4().hex[:6]}")

    # Atendimento da empresa A, criado pelo fluxo de IAM e já com senha definitiva
    r = c.post("/usuarios", headers=ctx["h_a"],
               json={"nome": "Atendente Clientes", "email": f"atend.{uuid.uuid4().hex[:10]}@teste.local"})
    email, temporaria = r.get_json()["usuario"]["email"], r.get_json()["senha_temporaria"]
    token = c.post("/auth/login", json={"email": email, "senha": temporaria}).get_json()["token"]
    r = c.put("/auth/senha", headers={"Authorization": f"Bearer {token}"},
              json={"senha_atual": temporaria, "nova_senha": "Atendente#2026x"})
    ctx["h_at"] = {"Authorization": f"Bearer {r.get_json()['token']}"}


def tearDownModule():
    for empresa_id in ctx.get("empresas", []):
        for tabela in ("auditoria_usuarios", "interacoes", "tarefas", "oportunidades",
                       "clientes", "configuracoes", "usuarios"):
            sql(f"DELETE FROM {tabela} WHERE empresa_id = %s;", (empresa_id,))
        sql("DELETE FROM empresas WHERE id = %s;", (empresa_id,))


def novo_cliente(**extra):
    corpo = {"nome": "Cliente Original", "email": "original@exemplo.com",
             "telefone": "(11) 90000-0000", "status": "Lead", **extra}
    r = c.post("/clientes", headers=ctx["h_a"], json=corpo)
    assert r.status_code == 201, r.get_json()
    return r.get_json()["cliente_id"]


def ler(cliente_id, headers=None):
    return c.get(f"/clientes/{cliente_id}", headers=headers or ctx["h_a"]).get_json()


class EdicaoParcial(unittest.TestCase):

    def test_01_alterar_so_o_telefone_preserva_o_resto(self):
        """Dado um cliente completo / Quando altero só o telefone /
        Então e-mail, nome e status continuam (antes eram apagados)."""
        cid = novo_cliente()
        r = c.put(f"/clientes/{cid}", headers=ctx["h_a"], json={"telefone": "(21) 98888-7777"})
        self.assertEqual(r.status_code, 200, r.get_json())

        dados = ler(cid)
        self.assertEqual(dados["telefone"], "(21) 98888-7777")
        self.assertEqual(dados["email"], "original@exemplo.com")
        self.assertEqual(dados["nome"], "Cliente Original")
        self.assertEqual(dados["status"], "Lead")

    def test_02_mudar_status_no_ciclo_lead_cliente_inativo(self):
        cid = novo_cliente()
        for status in ("Cliente", "Inativo", "Lead"):
            with self.subTest(status=status):
                r = c.put(f"/clientes/{cid}", headers=ctx["h_a"], json={"status": status})
                self.assertEqual(r.status_code, 200)
                self.assertEqual(ler(cid)["status"], status)

    def test_03_apagar_email_e_telefone_com_vazio(self):
        cid = novo_cliente()
        r = c.put(f"/clientes/{cid}", headers=ctx["h_a"], json={"email": "", "telefone": None})
        self.assertEqual(r.status_code, 200)
        dados = ler(cid)
        self.assertIsNone(dados["email"])
        self.assertIsNone(dados["telefone"])

    def test_04_normaliza_espacos_e_caixa_do_email(self):
        cid = novo_cliente()
        c.put(f"/clientes/{cid}", headers=ctx["h_a"], json={"nome": "  Nome Novo  ", "email": " Novo@Exemplo.COM "})
        dados = ler(cid)
        self.assertEqual(dados["nome"], "Nome Novo")
        self.assertEqual(dados["email"], "novo@exemplo.com")

    def test_05_registra_quem_alterou_e_quando(self):
        """Dado o Atendimento editando / Então o cliente mostra o autor da última alteração."""
        cid = novo_cliente()
        self.assertIsNone(ler(cid)["atualizado_em"])
        r = c.put(f"/clientes/{cid}", headers=ctx["h_at"], json={"status": "Cliente"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["cliente"]["atualizado_por_nome"], "Atendente Clientes")
        self.assertIsNotNone(ler(cid)["atualizado_em"])


class Validacoes(unittest.TestCase):

    def test_01_alteracoes_invalidas_sao_recusadas_sem_mudar_nada(self):
        cid = novo_cliente()
        invalidos = [
            {},
            {"nome": ""},
            {"nome": "   "},
            {"nome": "x" * 151},
            {"email": "sem-arroba"},
            {"email": 123},
            {"telefone": "abc"},
            {"telefone": "123"},
            {"telefone": "1" * 31},
            {"status": "Ganho"},
            {"status": None},
        ]
        for corpo in invalidos:
            with self.subTest(corpo=str(corpo)[:50]):
                self.assertEqual(c.put(f"/clientes/{cid}", headers=ctx["h_a"], json=corpo).status_code, 400)

        dados = ler(cid)
        self.assertEqual((dados["nome"], dados["email"], dados["status"]),
                         ("Cliente Original", "original@exemplo.com", "Lead"))

    def test_02_criacao_usa_as_mesmas_regras(self):
        for corpo in ({"nome": ""}, {"nome": "X", "status": "VIP"}, {"nome": "X", "email": "invalido"}):
            with self.subTest(corpo=corpo):
                self.assertEqual(c.post("/clientes", headers=ctx["h_a"], json=corpo).status_code, 400)
        r = c.post("/clientes", headers=ctx["h_a"], json={"nome": "Só o nome"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(ler(r.get_json()["cliente_id"])["status"], "Lead")

    def test_03_banco_tambem_recusa_status_fora_da_lista(self):
        """Mesmo por fora da API, o banco não aceita status inválido."""
        cid = novo_cliente()
        with self.assertRaises(Exception):
            sql("UPDATE clientes SET status = 'Ganho' WHERE id = %s;", (cid,))


class Permissoes(unittest.TestCase):

    def test_01_outra_empresa_nao_le_nem_altera(self):
        cid = novo_cliente()
        self.assertEqual(c.get(f"/clientes/{cid}", headers=ctx["h_b"]).status_code, 404)
        self.assertEqual(c.put(f"/clientes/{cid}", headers=ctx["h_b"], json={"nome": "Invasão"}).status_code, 404)
        self.assertEqual(ler(cid)["nome"], "Cliente Original")

    def test_02_atendimento_cria_e_edita_mas_nao_exclui(self):
        r = c.post("/clientes", headers=ctx["h_at"], json={"nome": "Do atendimento"})
        self.assertEqual(r.status_code, 201)
        cid = r.get_json()["cliente_id"]
        self.assertEqual(c.put(f"/clientes/{cid}", headers=ctx["h_at"], json={"status": "Cliente"}).status_code, 200)
        self.assertEqual(c.delete(f"/clientes/{cid}", headers=ctx["h_at"]).status_code, 403)
        self.assertEqual(c.delete(f"/clientes/{cid}", headers=ctx["h_a"]).status_code, 200)

    def test_03_sem_token_nada_funciona(self):
        cid = novo_cliente()
        self.assertEqual(c.put(f"/clientes/{cid}", json={"nome": "X"}).status_code, 401)


if __name__ == "__main__":
    unittest.main(verbosity=2)
