"""BDD: IAM — criação, alteração, troca e redefinição de senha, desativação,
reativação, bloqueio por força bruta, sessões e auditoria.

    python3 -m unittest tests.test_iam_usuarios -v

Roda contra o banco do .env. Cria duas empresas de teste e remove tudo ao final.
"""
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone

import jwt

import app as aplicacao
from database.conexao import get_db_connection

SENHA_GESTOR = "Gestor#Teste2026"
c = aplicacao.app.test_client()
ctx = {}


def sql(consulta, parametros=()):
    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(consulta, parametros)
            resultado = cursor.fetchall() if cursor.description else None
        conexao.commit()
    return resultado


def email_unico(prefixo):
    return f"{prefixo}.{uuid.uuid4().hex[:10]}@teste.local"


def login(email, senha):
    return c.post("/auth/login", json={"email": email, "senha": senha})


def cabecalho(token):
    return {"Authorization": f"Bearer {token}"}


def registrar_empresa(nome):
    email = email_unico("gestor")
    r = c.post("/auth/register", json={"nome_empresa": nome, "nome_usuario": f"Gestor {nome}",
                                       "email": email, "senha": SENHA_GESTOR})
    assert r.status_code == 201, r.get_json()
    ctx.setdefault("empresas", []).append(r.get_json()["empresa_id"])
    sessao = login(email, SENHA_GESTOR).get_json()
    return {"email": email, "id": r.get_json()["usuario_id"], "h": cabecalho(sessao["token"])}


def criar_usuario(headers, perfil="Atendimento", nome="Usuário Teste"):
    email = email_unico("usuario")
    r = c.post("/usuarios", headers=headers, json={"nome": nome, "email": email, "perfil": perfil})
    assert r.status_code == 201, r.get_json()
    corpo = r.get_json()
    return {"email": email, "id": corpo["usuario"]["id"], "temporaria": corpo["senha_temporaria"]}


def ativar_com_senha_definitiva(usuario, nova="Definitiva#2026x"):
    """Primeiro acesso: entra com a temporária e troca. Devolve o token final."""
    token = login(usuario["email"], usuario["temporaria"]).get_json()["token"]
    r = c.put("/auth/senha", headers=cabecalho(token),
              json={"senha_atual": usuario["temporaria"], "nova_senha": nova})
    assert r.status_code == 200, r.get_json()
    usuario["senha"] = nova
    return r.get_json()["token"]


def acoes_auditadas(empresa_headers, alvo_id):
    eventos = c.get("/usuarios/auditoria?limite=200", headers=empresa_headers).get_json()
    return [e["acao"] for e in eventos if e["alvo_id"] == alvo_id]


def setUpModule():
    ctx["a"] = registrar_empresa(f"Empresa A IAM {uuid.uuid4().hex[:6]}")
    ctx["b"] = registrar_empresa(f"Empresa B IAM {uuid.uuid4().hex[:6]}")


def tearDownModule():
    for empresa_id in ctx.get("empresas", []):
        for tabela in ("auditoria_usuarios", "interacoes", "tarefas", "oportunidades",
                       "clientes", "configuracoes", "usuarios"):
            sql(f"DELETE FROM {tabela} WHERE empresa_id = %s;", (empresa_id,))
        sql("DELETE FROM empresas WHERE id = %s;", (empresa_id,))


class LoginSemEnumeracao(unittest.TestCase):

    def test_01_email_inexistente_e_senha_errada_respondem_igual(self):
        """Então não dá para descobrir quais e-mails têm conta."""
        r1 = login(email_unico("ninguem"), "Qualquer#Senha1")
        r2 = login(ctx["a"]["email"], "Senha#Errada123")
        self.assertEqual((r1.status_code, r1.get_json()), (r2.status_code, r2.get_json()))
        self.assertEqual(r1.status_code, 401)
        self.assertEqual(r1.get_json(), {"erro": "E-mail ou senha inválidos."})

    def test_02_email_sem_diferenciar_maiusculas(self):
        r = login("  " + ctx["a"]["email"].upper() + " ", SENHA_GESTOR)
        self.assertEqual(r.status_code, 200, r.get_json())

    def test_03_rota_publica_antiga_de_dados_foi_removida(self):
        """Dado o antigo GET /auth/me/<id> sem token / Então não existe mais."""
        self.assertEqual(c.get(f"/auth/me/{ctx['a']['id']}").status_code, 404)
        self.assertEqual(c.get("/auth/me").status_code, 401)
        r = c.get("/auth/me", headers=ctx["a"]["h"])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["email"], ctx["a"]["email"])
        self.assertNotIn("senha", r.get_json())

    def test_04_token_sem_versao_de_sessao_e_recusado(self):
        """Dado um token no formato antigo (sem 'ver') / Então 401."""
        antigo = jwt.encode({"sub": str(ctx["a"]["id"]), "empresa_id": ctx["empresas"][0],
                             "perfil": "Gestor", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                            os.environ["SECRET_KEY"], algorithm="HS256")
        self.assertEqual(c.get("/clientes", headers=cabecalho(antigo)).status_code, 401)


class PoliticaDeSenha(unittest.TestCase):

    def cadastrar(self, senha, email=None):
        return c.post("/auth/register", json={"nome_empresa": "Política", "nome_usuario": "X",
                                              "email": email or email_unico("politica"), "senha": senha})

    def test_01_senhas_fracas_sao_recusadas(self):
        email = email_unico("politica")
        for senha, motivo in [("curta1", "10 caracteres"), ("1234567890", "comum"),
                              ("senha12345", "comum"), ("aaaaaaaaaaaa", "comum"),
                              (email, "e-mail"), (email.split("@")[0], "e-mail"),
                              ("ç" * 37, "72 bytes"), (None, "obrigatória")]:
            with self.subTest(motivo=motivo):
                r = self.cadastrar(senha, email)
                self.assertEqual(r.status_code, 400, r.get_json())

    def test_02_limite_de_72_bytes_aceito_sem_erro_500(self):
        email = email_unico("politica")
        r = self.cadastrar("Ab3" + "x" * 69, email)  # exatamente 72 bytes
        self.assertEqual(r.status_code, 201, r.get_json())
        ctx["empresas"].append(r.get_json()["empresa_id"])
        self.assertEqual(login(email, "Ab3" + "x" * 69).status_code, 200)
        self.assertEqual(login(email, "Ab3" + "x" * 70).status_code, 401)  # 73 bytes: nunca autentica

    def test_03_email_duplicado_mesmo_com_outra_caixa(self):
        r = self.cadastrar("Nova#Empresa2026", ctx["a"]["email"].upper())
        self.assertEqual(r.status_code, 409)


class CriacaoEPrimeiroAcesso(unittest.TestCase):

    def test_01_gestor_cria_usuario_com_senha_temporaria(self):
        """Dado o Gestor / Quando cria um Atendimento / Então recebe a senha temporária uma vez."""
        u = criar_usuario(ctx["a"]["h"])
        self.assertEqual(len(u["temporaria"]), 14)
        lista = c.get("/usuarios", headers=ctx["a"]["h"]).get_json()
        novo = next(x for x in lista if x["id"] == u["id"])
        self.assertTrue(novo["deve_trocar_senha"])
        self.assertIsNotNone(novo["senha_temporaria_expira_em"])
        self.assertNotIn("senha", novo)
        self.assertNotIn(u["temporaria"], str(lista))
        self.assertIn("usuario_criado", acoes_auditadas(ctx["a"]["h"], u["id"]))

    def test_02_troca_obrigatoria_bloqueia_o_resto_do_sistema(self):
        """Dado o primeiro acesso / Então só dá para trocar a senha e ver os próprios dados."""
        u = criar_usuario(ctx["a"]["h"])
        r = login(u["email"], u["temporaria"])
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["usuario"]["deve_trocar_senha"])
        h = cabecalho(r.get_json()["token"])

        r = c.get("/clientes", headers=h)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["error"], "TROCA_SENHA_OBRIGATORIA")
        self.assertEqual(c.get("/auth/me", headers=h).status_code, 200)

        for corpo, motivo in [({"senha_atual": "errada#123456", "nova_senha": "Nova#Senha2026"}, "atual errada"),
                              ({"senha_atual": u["temporaria"], "nova_senha": u["temporaria"]}, "igual"),
                              ({"senha_atual": u["temporaria"], "nova_senha": "1234567890"}, "fraca")]:
            with self.subTest(motivo=motivo):
                self.assertEqual(c.put("/auth/senha", headers=h, json=corpo).status_code, 400)

        r = c.put("/auth/senha", headers=h, json={"senha_atual": u["temporaria"], "nova_senha": "Nova#Senha2026"})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertFalse(r.get_json()["usuario"]["deve_trocar_senha"])

        self.assertEqual(c.get("/clientes", headers=h).status_code, 401, "token anterior deve cair")
        self.assertEqual(c.get("/clientes", headers=cabecalho(r.get_json()["token"])).status_code, 200)
        self.assertEqual(login(u["email"], u["temporaria"]).status_code, 401)
        self.assertIn("senha_alterada", acoes_auditadas(ctx["a"]["h"], u["id"]))

    def test_03_senha_temporaria_expira(self):
        u = criar_usuario(ctx["a"]["h"])
        sql("UPDATE usuarios SET senha_temporaria_expira_em = NOW() - INTERVAL '1 minute' WHERE id = %s;",
            (u["id"],))
        r = login(u["email"], u["temporaria"])
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.get_json()["error"], "SENHA_TEMPORARIA_EXPIRADA")

    def test_04_validacoes_e_email_duplicado(self):
        h = ctx["a"]["h"]
        for corpo in ({"nome": "", "email": email_unico("x")},
                      {"nome": "X", "email": "sem-arroba"},
                      {"nome": "X", "email": email_unico("x"), "perfil": "Admin"}):
            with self.subTest(corpo=corpo):
                self.assertEqual(c.post("/usuarios", headers=h, json=corpo).status_code, 400)
        r = c.post("/usuarios", headers=h, json={"nome": "Dup", "email": ctx["b"]["email"].upper()})
        self.assertEqual(r.status_code, 409)

    def test_05_atendimento_nao_administra_usuarios(self):
        u = criar_usuario(ctx["a"]["h"])
        h = cabecalho(ativar_com_senha_definitiva(u))
        self.assertEqual(c.get("/usuarios", headers=h).status_code, 403)
        self.assertEqual(c.post("/usuarios", headers=h, json={"nome": "X", "email": email_unico("x")}).status_code, 403)
        self.assertEqual(c.put(f"/usuarios/{u['id']}", headers=h, json={"perfil": "Gestor"}).status_code, 403)
        self.assertEqual(c.get("/usuarios/auditoria", headers=h).status_code, 403)


class AlteracaoEPerfil(unittest.TestCase):

    def test_01_alterar_nome_e_email(self):
        u = criar_usuario(ctx["a"]["h"])
        novo_email = email_unico("renomeado")
        r = c.put(f"/usuarios/{u['id']}", headers=ctx["a"]["h"], json={"nome": "Nome Novo", "email": novo_email.upper()})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["usuario"]["email"], novo_email)
        self.assertEqual(login(novo_email, u["temporaria"]).status_code, 200)
        self.assertIn("usuario_alterado", acoes_auditadas(ctx["a"]["h"], u["id"]))

    def test_02_mudar_perfil_derruba_sessoes_do_usuario(self):
        """Dado um Atendimento logado / Quando vira Gestor / Então a sessão antiga cai e
        o novo login já vem como Gestor."""
        u = criar_usuario(ctx["a"]["h"])
        token = ativar_com_senha_definitiva(u)
        r = c.put(f"/usuarios/{u['id']}", headers=ctx["a"]["h"], json={"perfil": "Gestor"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(c.get("/clientes", headers=cabecalho(token)).status_code, 401)
        self.assertEqual(login(u["email"], u["senha"]).get_json()["usuario"]["perfil"], "Gestor")
        self.assertIn("perfil_alterado", acoes_auditadas(ctx["a"]["h"], u["id"]))

    def test_03_ninguem_altera_o_proprio_perfil(self):
        r = c.put(f"/usuarios/{ctx['a']['id']}", headers=ctx["a"]["h"], json={"perfil": "Atendimento"})
        self.assertEqual(r.status_code, 409)
        r = c.put(f"/usuarios/{ctx['a']['id']}", headers=ctx["a"]["h"], json={"nome": "Gestor A Renomeado"})
        self.assertEqual(r.status_code, 200, "o próprio nome pode")

    def test_04_isolamento_entre_empresas(self):
        """Dado o Gestor da empresa B / Então não vê nem mexe em usuários de A."""
        u = criar_usuario(ctx["a"]["h"])
        hb = ctx["b"]["h"]
        self.assertNotIn(u["id"], [x["id"] for x in c.get("/usuarios", headers=hb).get_json()])
        self.assertEqual(c.put(f"/usuarios/{u['id']}", headers=hb, json={"nome": "Invasão"}).status_code, 404)
        for acao in ("redefinir-senha", "desativar", "reativar"):
            with self.subTest(acao=acao):
                self.assertEqual(c.post(f"/usuarios/{u['id']}/{acao}", headers=hb).status_code, 404)
        self.assertNotIn(u["id"], [e["alvo_id"] for e in c.get("/usuarios/auditoria", headers=hb).get_json()])


class DesativacaoReativacaoERedefinicao(unittest.TestCase):

    def test_01_desativar_encerra_sessao_e_impede_login(self):
        u = criar_usuario(ctx["a"]["h"])
        token = ativar_com_senha_definitiva(u)
        r = c.post(f"/usuarios/{u['id']}/desativar", headers=ctx["a"]["h"])
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.get_json()["usuario"]["ativo"])

        r = c.get("/clientes", headers=cabecalho(token))
        self.assertEqual((r.status_code, r.get_json()["error"]), (401, "CONTA_DESATIVADA"))
        r = login(u["email"], u["senha"])
        self.assertEqual((r.status_code, r.get_json()["error"]), (403, "CONTA_DESATIVADA"))
        self.assertEqual(login(u["email"], "Senha#Errada123").get_json(), {"erro": "E-mail ou senha inválidos."},
                         "com senha errada não revela que a conta existe")
        self.assertEqual(c.post(f"/usuarios/{u['id']}/desativar", headers=ctx["a"]["h"]).status_code, 409)
        self.assertEqual(c.post(f"/usuarios/{u['id']}/redefinir-senha", headers=ctx["a"]["h"]).status_code, 409)

    def test_02_reativar_exige_senha_nova(self):
        """Dado uma conta desativada / Quando reativada / Então a senha antiga não vale mais."""
        u = criar_usuario(ctx["a"]["h"])
        ativar_com_senha_definitiva(u)
        c.post(f"/usuarios/{u['id']}/desativar", headers=ctx["a"]["h"])

        r = c.post(f"/usuarios/{u['id']}/reativar", headers=ctx["a"]["h"])
        self.assertEqual(r.status_code, 200, r.get_json())
        temporaria = r.get_json()["senha_temporaria"]
        self.assertTrue(r.get_json()["usuario"]["ativo"])

        self.assertEqual(login(u["email"], u["senha"]).status_code, 401)
        r = login(u["email"], temporaria)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.get_json()["usuario"]["deve_trocar_senha"])
        self.assertEqual(c.post(f"/usuarios/{u['id']}/reativar", headers=ctx["a"]["h"]).status_code, 409)
        self.assertIn("usuario_reativado", acoes_auditadas(ctx["a"]["h"], u["id"]))

    def test_03_gestor_nao_age_sobre_a_propria_conta(self):
        for acao in ("desativar", "redefinir-senha", "reativar"):
            with self.subTest(acao=acao):
                self.assertEqual(c.post(f"/usuarios/{ctx['a']['id']}/{acao}", headers=ctx["a"]["h"]).status_code, 409)
        self.assertEqual(c.get("/clientes", headers=ctx["a"]["h"]).status_code, 200)

    def test_04_forca_bruta_bloqueia_e_redefinicao_libera(self):
        """Dado 5 senhas erradas / Então a conta bloqueia, inclusive para a senha certa;
        a redefinição pelo Gestor desbloqueia."""
        u = criar_usuario(ctx["a"]["h"])
        ativar_com_senha_definitiva(u)
        for _ in range(5):
            self.assertEqual(login(u["email"], "Senha#Errada123").status_code, 401)

        r = login(u["email"], u["senha"])
        self.assertEqual((r.status_code, r.get_json()["error"]), (429, "LOGIN_BLOQUEADO"))
        self.assertTrue(next(x for x in c.get("/usuarios", headers=ctx["a"]["h"]).get_json()
                             if x["id"] == u["id"])["bloqueado"])
        self.assertIn("login_bloqueado", acoes_auditadas(ctx["a"]["h"], u["id"]))

        r = c.post(f"/usuarios/{u['id']}/redefinir-senha", headers=ctx["a"]["h"])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(login(u["email"], r.get_json()["senha_temporaria"]).status_code, 200)
        self.assertIn("senha_redefinida", acoes_auditadas(ctx["a"]["h"], u["id"]))

    def test_05_redefinir_derruba_sessoes_abertas(self):
        u = criar_usuario(ctx["a"]["h"])
        token = ativar_com_senha_definitiva(u)
        c.post(f"/usuarios/{u['id']}/redefinir-senha", headers=ctx["a"]["h"])
        self.assertEqual(c.get("/clientes", headers=cabecalho(token)).status_code, 401)
        self.assertEqual(login(u["email"], u["senha"]).status_code, 401)


class Auditoria(unittest.TestCase):

    def test_01_auditoria_nunca_guarda_senhas(self):
        """Então nenhum evento contém senha, hash ou token."""
        u = criar_usuario(ctx["a"]["h"])
        ativar_com_senha_definitiva(u, nova="Segredo#Audit2026")
        brutos = sql("SELECT detalhes::text FROM auditoria_usuarios WHERE empresa_id = %s;", (ctx["empresas"][0],))
        tudo = " ".join(linha[0] for linha in brutos)
        for proibido in (u["temporaria"], "Segredo#Audit2026", "$2b$", "senha_hash", "token"):
            with self.subTest(proibido=proibido):
                self.assertNotIn(proibido, tudo)

    def test_02_registra_ator_alvo_e_ip(self):
        u = criar_usuario(ctx["a"]["h"])
        linha = sql("""SELECT ator_id, alvo_id, acao, ip FROM auditoria_usuarios
                       WHERE alvo_id = %s AND acao = 'usuario_criado';""", (u["id"],))[0]
        self.assertEqual(linha[:3], (ctx["a"]["id"], u["id"], "usuario_criado"))
        self.assertTrue(linha[3])


if __name__ == "__main__":
    unittest.main(verbosity=2)
