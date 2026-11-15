"""BDD: exportação do faturamento em PDF com a marca SANDRO CRM.

    python3 -m unittest tests.test_pdf_faturamento -v

Roda contra o banco do .env. Cria duas empresas de teste e remove tudo ao final.
"""
import base64
import re
import unittest
import uuid
import zlib

import bcrypt

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


def texto_do_pdf(dados):
    """Junta o conteúdo (descomprimido) das páginas para procurar textos."""
    partes = []
    for bruto in re.findall(rb"stream\r?\n(.*?)\r?\n?endstream", dados, re.S):
        bruto = bruto.strip()
        try:
            # reportlab grava o conteúdo com /ASCII85Decode /FlateDecode
            if bruto.endswith(b"~>"):
                bruto = base64.a85decode(bruto, adobe=True) if bruto.startswith(b"<~") \
                    else base64.a85decode(b"<~" + bruto, adobe=True)
            partes.append(zlib.decompress(bruto))
        except (ValueError, zlib.error):
            partes.append(bruto)
    texto = b"\n".join(partes).decode("latin-1")
    # Desfaz os escapes de string do PDF: \( \) \\
    return re.sub(r"\\([()\\])", r"\1", texto)


def registrar(nome):
    email = f"gestor.{uuid.uuid4().hex[:10]}@teste.local"
    r = c.post("/auth/register", json={"nome_empresa": nome, "nome_usuario": "Gestora PDF",
                                       "email": email, "senha": SENHA})
    assert r.status_code == 201, r.get_json()
    ctx.setdefault("empresas", []).append(r.get_json()["empresa_id"])
    token = c.post("/auth/login", json={"email": email, "senha": SENHA}).get_json()["token"]
    return r.get_json()["empresa_id"], {"Authorization": f"Bearer {token}"}


def setUpModule():
    ctx["empresa_a"], ctx["h_a"] = registrar(f"Empresa A PDF {uuid.uuid4().hex[:6]}")
    _, ctx["h_b"] = registrar(f"Empresa B PDF {uuid.uuid4().hex[:6]}")

    email_at = f"atend.{uuid.uuid4().hex[:10]}@teste.local"
    sql("""INSERT INTO usuarios (empresa_id, nome, email, senha, perfil)
           VALUES (%s, 'Atendente PDF', %s, %s, 'Atendimento');""",
        (ctx["empresa_a"], email_at, bcrypt.hashpw(SENHA.encode(), bcrypt.gensalt()).decode()))
    token = c.post("/auth/login", json={"email": email_at, "senha": SENHA}).get_json()["token"]
    ctx["h_at"] = {"Authorization": f"Bearer {token}"}

    cliente = c.post("/clientes", headers=ctx["h_a"], json={"nome": "Cliente PDF"}).get_json()["cliente_id"]
    ctx["malicioso"] = '<font color="red">INJETADO</font><a href="javascript:alert(1)">link</a>'
    for titulo, valor in ((ctx["malicioso"], 100), ("Venda normal", 250.5)):
        r = c.post("/oportunidades", headers=ctx["h_a"], json={
            "cliente_id": cliente, "titulo": titulo, "valor": valor, "etapa": "Fechado"})
        assert r.status_code == 201, r.get_json()

    cliente_b = c.post("/clientes", headers=ctx["h_b"], json={"nome": "Cliente B"}).get_json()["cliente_id"]
    c.post("/oportunidades", headers=ctx["h_b"], json={
        "cliente_id": cliente_b, "titulo": "SEGREDO DA EMPRESA B", "valor": 999, "etapa": "Fechado"})


def tearDownModule():
    for empresa_id in ctx.get("empresas", []):
        for tabela in ("auditoria_usuarios", "interacoes", "tarefas", "oportunidades",
                       "clientes", "configuracoes", "usuarios"):
            sql(f"DELETE FROM {tabela} WHERE empresa_id = %s;", (empresa_id,))
        sql("DELETE FROM empresas WHERE id = %s;", (empresa_id,))


def baixar(periodo="mes", headers=None):
    return c.get(f"/relatorios/vendas/pdf?periodo={periodo}", headers=headers or ctx["h_a"])


class ExportarPdf(unittest.TestCase):

    def test_01_gera_pdf_valido_para_download(self):
        r = baixar()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "application/pdf")
        self.assertTrue(r.data.startswith(b"%PDF-"))
        self.assertTrue(r.data.rstrip().endswith(b"%%EOF"))
        self.assertRegex(r.headers["Content-Disposition"],
                         r'^attachment; filename="faturamento-empresa-a-pdf-[a-f0-9]{6}-mes-\d{4}-\d{2}-\d{2}\.pdf"$')
        self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_02_tem_a_marca_e_os_numeros_da_tela(self):
        texto = texto_do_pdf(baixar().data)
        for esperado in ("SANDRO", "CRM", "Relat", "Faturamento", "Gestora PDF", "Venda normal",
                         "R$ 350,50", "R$ 250,50", "2 vendas"):
            with self.subTest(esperado=esperado):
                self.assertIn(esperado, texto)
        self.assertIn(b"/Author (SANDRO CRM)", baixar().data)

    def test_03_marcacao_no_titulo_sai_como_texto(self):
        """Dado um título com <font> e <a href> / Então aparece literal no PDF, sem virar formatação nem link."""
        dados = baixar().data
        texto = texto_do_pdf(dados)
        # O texto vem fatiado em vários "(...) Tj": junta para ler como o leitor de PDF
        corrido = re.sub(r"\)\s*Tj\s*(?:T\*\s*)?\(", "", texto)
        self.assertIn('<font color="red">INJETADO</font><a', corrido)
        self.assertIn('href="javascript:alert(1)">link</a>', corrido)
        self.assertNotIn(b"/URI", dados)
        self.assertNotIn(b"javascript", dados.replace(texto.encode("latin-1"), b""))

    def test_04_isolamento_entre_empresas(self):
        self.assertNotIn("SEGREDO DA EMPRESA B", texto_do_pdf(baixar().data))

    def test_05_permissoes_e_validacao(self):
        self.assertEqual(c.get("/relatorios/vendas/pdf?periodo=mes").status_code, 401)
        self.assertEqual(baixar(headers=ctx["h_at"]).status_code, 403)
        self.assertEqual(baixar("semana").status_code, 400)

    def test_06_muitas_vendas_viram_varias_paginas_numeradas(self):
        cliente = c.post("/clientes", headers=ctx["h_a"], json={"nome": "Cliente Volume"}).get_json()["cliente_id"]
        sql("""INSERT INTO oportunidades (empresa_id, cliente_id, titulo, valor, etapa, responsavel_id)
               SELECT %s, %s, 'Venda em volume ' || n, 10, 'Fechado', NULL FROM generate_series(1, 120) n;""",
            (ctx["empresa_a"], cliente))
        texto = texto_do_pdf(baixar("total").data)
        paginas = re.findall(r"P\S*gina (\d+) de (\d+)", texto)
        self.assertGreaterEqual(len(paginas), 3)
        total = paginas[0][1]
        self.assertTrue(all(t == total for _, t in paginas))
        self.assertIn("Venda em volume 120", texto)

    def test_07_periodo_sem_vendas_gera_pdf_com_aviso(self):
        _, h_vazia = registrar(f"Empresa Vazia PDF {uuid.uuid4().hex[:6]}")
        r = baixar(headers=h_vazia)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Nenhuma venda fechada", texto_do_pdf(r.data))


if __name__ == "__main__":
    unittest.main(verbosity=2)
