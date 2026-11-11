"""BDD: janela de acesso por horário e reciclagem pós-venda.

Roda contra o banco do .env (homologação). Cria duas empresas de teste com
e-mails únicos e remove todos os dados ao final, mesmo se algo falhar.

Uso (na raiz do projeto, depois de aplicar as migrações):
    python3 -m unittest tests.test_reciclagem_horarios -v
"""
import contextlib
import io
import re
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone

import bcrypt

import app as aplicacao
from database import worker_reciclagem
from database.conexao import conectar_banco
from seguranca import TZ_EMPRESA


SENHA = "Senha@Teste123"
RE_MENSAGEM = re.compile(r"^Acesso permitido apenas entre \d{2}:\d{2} e \d{2}:\d{2}$")

cliente_http = aplicacao.app.test_client()
contexto = {}


# ---------------------------------------------------------------------------
# Apoio
# ---------------------------------------------------------------------------

def sql(consulta, parametros=()):
    conexao = conectar_banco()
    try:
        with conexao.cursor() as cursor:
            cursor.execute(consulta, parametros)
            resultado = cursor.fetchone() if cursor.description else None
        conexao.commit()
        return resultado
    finally:
        conexao.close()


def hora_local():
    """Hora atual no fuso da empresa, lida do próprio banco."""
    return sql("SELECT (NOW() AT TIME ZONE %s)::time;", (TZ_EMPRESA,))[0]


def deslocar(horas):
    base = datetime.combine(date(2000, 1, 1), hora_local())
    return (base + timedelta(hours=horas)).strftime("%H:%M")


def registrar(empresa, usuario, email):
    r = cliente_http.post("/auth/register", json={
        "nome_empresa": empresa, "nome_usuario": usuario,
        "email": email, "senha": SENHA
    })
    assert r.status_code == 201, f"register falhou: {r.status_code} {r.get_json()}"
    corpo = r.get_json()
    contexto.setdefault("empresas", []).append(corpo["empresa_id"])
    return corpo["empresa_id"], corpo["usuario_id"]


def login(email, senha=SENHA):
    return cliente_http.post("/auth/login", json={"email": email, "senha": senha})


def cabecalho(email):
    r = login(email)
    assert r.status_code == 200, f"login falhou: {r.status_code} {r.get_json()}"
    return {"Authorization": f"Bearer {r.get_json()['token']}"}


def definir_janela_sql(usuario_id, inicio, fim):
    sql("UPDATE usuarios SET hora_inicio_acesso = %s, hora_fim_acesso = %s WHERE id = %s;",
        (inicio, fim, usuario_id))


def setUpModule():
    sufixo = uuid.uuid4().hex[:8]
    contexto["email_gestor_a"] = f"gestor.a.{sufixo}@teste.local"
    contexto["email_gestor_b"] = f"gestor.b.{sufixo}@teste.local"
    contexto["email_atend_a"] = f"atend.a.{sufixo}@teste.local"

    contexto["empresa_a"], contexto["gestor_a_id"] = registrar(
        "Empresa A QA", "Gestor A", contexto["email_gestor_a"])
    contexto["empresa_b"], _ = registrar(
        "Empresa B QA", "Gestor B", contexto["email_gestor_b"])

    senha_hash = bcrypt.hashpw(SENHA.encode(), bcrypt.gensalt()).decode()
    contexto["atend_a_id"] = sql("""
        INSERT INTO usuarios (empresa_id, nome, email, senha, perfil)
        VALUES (%s, 'Atendente A', %s, %s, 'Atendimento')
        RETURNING id;
    """, (contexto["empresa_a"], contexto["email_atend_a"], senha_hash))[0]

    contexto["h_gestor_a"] = cabecalho(contexto["email_gestor_a"])
    contexto["h_gestor_b"] = cabecalho(contexto["email_gestor_b"])


def tearDownModule():
    for empresa_id in contexto.get("empresas", []):
        for tabela in ("tarefas", "oportunidades", "clientes", "configuracoes", "usuarios"):
            sql(f"DELETE FROM {tabela} WHERE empresa_id = %s;", (empresa_id,))
        sql("DELETE FROM empresas WHERE id = %s;", (empresa_id,))


# ---------------------------------------------------------------------------
# Funcionalidade: Controle de acesso por horário
# ---------------------------------------------------------------------------

class TravaDeHorario(unittest.TestCase):

    def setUp(self):
        definir_janela_sql(contexto["atend_a_id"], None, None)
        self.url_atend = f"/configuracoes/usuarios/{contexto['atend_a_id']}"

    def test_01_login_sem_janela_e_liberado(self):
        """Dado um usuário sem janela (NULL) / Quando faz login / Então recebe token."""
        r = login(contexto["email_atend_a"])
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.get_json())

    def test_02_login_fora_da_janela_e_bloqueado(self):
        """Dado uma janela que não inclui agora / Quando faz login /
        Então recebe 403 HORARIO_BLOQUEADO com a janela na mensagem e sem token."""
        inicio, fim = deslocar(1), deslocar(2)
        definir_janela_sql(contexto["atend_a_id"], inicio, fim)

        r = login(contexto["email_atend_a"])
        corpo = r.get_json()

        self.assertEqual(r.status_code, 403)
        self.assertEqual(corpo["error"], "HORARIO_BLOQUEADO")
        self.assertRegex(corpo["message"], RE_MENSAGEM)
        self.assertEqual(corpo["message"], f"Acesso permitido apenas entre {inicio} e {fim}")
        self.assertNotIn("token", corpo)

    def test_03_janela_que_cruza_meia_noite(self):
        """Dado início > fim (ex.: 22:00-06:00) / Então vale a faixa circular:
        uma janela que contém agora libera, e a complementar bloqueia."""
        definir_janela_sql(contexto["atend_a_id"], deslocar(-1), deslocar(-2))
        self.assertEqual(login(contexto["email_atend_a"]).status_code, 200)

        definir_janela_sql(contexto["atend_a_id"], deslocar(1), deslocar(-1))
        self.assertEqual(login(contexto["email_atend_a"]).status_code, 403)

    def test_04_janela_expira_com_sessao_ativa(self):
        """Dado um Atendimento logado / Quando o Gestor fecha a janela dele /
        Então a próxima requisição com o MESMO token recebe 403 HORARIO_BLOQUEADO."""
        h_atend = cabecalho(contexto["email_atend_a"])
        self.assertEqual(cliente_http.get("/clientes", headers=h_atend).status_code, 200)

        r = cliente_http.put(self.url_atend, headers=contexto["h_gestor_a"], json={
            "hora_inicio_acesso": deslocar(1), "hora_fim_acesso": deslocar(2)
        })
        self.assertEqual(r.status_code, 200, r.get_json())

        r = cliente_http.get("/clientes", headers=h_atend)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.get_json()["error"], "HORARIO_BLOQUEADO")

    def test_05_senha_errada_nao_revela_janela(self):
        """Dado janela fechada / Quando erra a senha / Então recebe 401, sem expor horários."""
        definir_janela_sql(contexto["atend_a_id"], deslocar(1), deslocar(2))
        r = login(contexto["email_atend_a"], "senha-errada")
        self.assertEqual(r.status_code, 401)
        self.assertNotIn("error", r.get_json())

    def test_06_somente_gestor_altera_horario(self):
        """Dado um Atendimento / Quando tenta alterar horários / Então recebe 403."""
        h_atend = cabecalho(contexto["email_atend_a"])
        r = cliente_http.put(self.url_atend, headers=h_atend, json={
            "hora_inicio_acesso": None, "hora_fim_acesso": None
        })
        self.assertEqual(r.status_code, 403)
        self.assertEqual(
            cliente_http.get("/configuracoes/usuarios", headers=h_atend).status_code, 403)

    def test_07_gestor_nao_altera_usuario_de_outra_empresa(self):
        """Dado o Gestor da empresa B / Quando altera usuário de A / Então recebe 404."""
        r = cliente_http.put(self.url_atend, headers=contexto["h_gestor_b"], json={
            "hora_inicio_acesso": "08:00", "hora_fim_acesso": "18:00"
        })
        self.assertEqual(r.status_code, 404)

    def test_08_validacoes_de_entrada(self):
        """Dado payloads inválidos / Então todos recebem 400 e nada é gravado."""
        invalidos = [
            {},
            {"hora_inicio_acesso": "08:00"},
            {"hora_inicio_acesso": "08:00", "hora_fim_acesso": None},
            {"hora_inicio_acesso": "25:00", "hora_fim_acesso": "18:00"},
            {"hora_inicio_acesso": "08:00", "hora_fim_acesso": "08:00"},
            {"hora_inicio_acesso": 8, "hora_fim_acesso": 18},
            {"hora_inicio_acesso": "8h", "hora_fim_acesso": "18h"},
        ]
        for corpo in invalidos:
            with self.subTest(corpo=corpo):
                r = cliente_http.put(self.url_atend, headers=contexto["h_gestor_a"], json=corpo)
                self.assertEqual(r.status_code, 400, r.get_json())

        janela = sql("SELECT hora_inicio_acesso FROM usuarios WHERE id = %s;",
                     (contexto["atend_a_id"],))[0]
        self.assertIsNone(janela)

    def test_09_gestor_nao_se_tranca_para_fora(self):
        """Dado o Gestor / Quando define para si uma janela que exclui agora /
        Então recebe 409 e continua com acesso."""
        url = f"/configuracoes/usuarios/{contexto['gestor_a_id']}"
        r = cliente_http.put(url, headers=contexto["h_gestor_a"], json={
            "hora_inicio_acesso": deslocar(1), "hora_fim_acesso": deslocar(2)
        })
        self.assertEqual(r.status_code, 409)
        self.assertEqual(
            cliente_http.get("/clientes", headers=contexto["h_gestor_a"]).status_code, 200)

    def test_10_listagem_mostra_status_e_isola_empresas(self):
        """Dado Atendimento bloqueado / Quando o Gestor lista usuários /
        Então vê Permitido/Bloqueado corretos e só usuários da própria empresa."""
        definir_janela_sql(contexto["atend_a_id"], deslocar(1), deslocar(2))

        lista = cliente_http.get("/configuracoes/usuarios",
                                 headers=contexto["h_gestor_a"]).get_json()
        por_id = {u["id"]: u for u in lista}

        self.assertFalse(por_id[contexto["atend_a_id"]]["acesso_permitido"])
        self.assertTrue(por_id[contexto["gestor_a_id"]]["acesso_permitido"])
        self.assertEqual(len(lista), 2)

        lista_b = cliente_http.get("/configuracoes/usuarios",
                                   headers=contexto["h_gestor_b"]).get_json()
        self.assertNotIn(contexto["atend_a_id"], [u["id"] for u in lista_b])


# ---------------------------------------------------------------------------
# Funcionalidade: Reciclagem automática pós-venda
# ---------------------------------------------------------------------------

class ReciclagemPosVenda(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        r = cliente_http.post("/clientes", headers=contexto["h_gestor_a"],
                              json={"nome": "Cliente Reciclagem"})
        assert r.status_code == 201, r.get_json()
        cls.cliente_id = r.get_json()["cliente_id"]

    def criar_oportunidade(self, etapa="Fechado", valor=1000):
        r = cliente_http.post("/oportunidades", headers=contexto["h_gestor_a"], json={
            "cliente_id": self.cliente_id, "titulo": f"Venda {uuid.uuid4().hex[:6]}",
            "valor": valor, "etapa": etapa
        })
        self.assertEqual(r.status_code, 201, r.get_json())
        return r.get_json()["oportunidade_id"]

    def agendar(self, op_id, corpo, headers=None):
        return cliente_http.post(f"/oportunidades/{op_id}/agendar-reciclagem",
                                 headers=headers or contexto["h_gestor_a"], json=corpo)

    def estado(self, op_id):
        return sql("""
            SELECT etapa, status_reciclagem, data_reciclagem_agendada
            FROM oportunidades WHERE id = %s;
        """, (op_id,))

    def test_01_agendar_por_periodo_relativo(self):
        """Dado uma venda Fechada / Quando agenda em 7 dias /
        Então fica 'pendente' para NOW() + 7 dias."""
        op = self.criar_oportunidade()
        r = self.agendar(op, {"dias": 7})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["status_reciclagem"], "pendente")

        diferenca = sql("""
            SELECT ABS(EXTRACT(EPOCH FROM data_reciclagem_agendada
                                         - (NOW() + INTERVAL '7 days')))
            FROM oportunidades WHERE id = %s;
        """, (op,))[0]
        self.assertLess(diferenca, 120)
        self.assertEqual(self.estado(op)[1], "pendente")

    def test_02_agendar_por_data_iso_utc(self):
        """Dado um ISO com Z / Então grava exatamente aquele instante."""
        op = self.criar_oportunidade()
        alvo = (datetime.now(timezone.utc) + timedelta(days=30)).replace(microsecond=0)
        r = self.agendar(op, {"data_agendada": alvo.strftime("%Y-%m-%dT%H:%M:%SZ")})
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(self.estado(op)[2], alvo)

    def test_03_agendar_somente_data_usa_fuso_da_empresa(self):
        """Dado 'AAAA-MM-DD' (input type=date) / Então agenda para a meia-noite
        no fuso da empresa, não em UTC."""
        op = self.criar_oportunidade()
        dia = (date.today() + timedelta(days=20)).isoformat()
        r = self.agendar(op, {"data_agendada": dia})
        self.assertEqual(r.status_code, 200, r.get_json())

        local = sql("""
            SELECT (data_reciclagem_agendada AT TIME ZONE %s)
            FROM oportunidades WHERE id = %s;
        """, (TZ_EMPRESA, op))[0]
        self.assertEqual(local, datetime.fromisoformat(dia))

    def test_04_rejeita_oportunidade_fora_da_etapa_final(self):
        """Dado uma oportunidade em Negociação / Quando agenda / Então recebe 409."""
        op = self.criar_oportunidade(etapa="Negociação")
        self.assertEqual(self.agendar(op, {"dias": 7}).status_code, 409)
        self.assertEqual(self.estado(op)[1], "nenhum")

    def test_05_rejeita_entradas_invalidas(self):
        """Dado payloads inválidos ou data no passado / Então recebe 400."""
        op = self.criar_oportunidade()
        ontem = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        invalidos = [
            {},
            {"dias": 7, "data_agendada": "2030-01-01"},
            {"dias": 0},
            {"dias": 366},
            {"dias": True},
            {"dias": "7"},
            {"data_agendada": "2030-13-01"},
            {"data_agendada": "amanhã"},
            {"data_agendada": ontem},
        ]
        for corpo in invalidos:
            with self.subTest(corpo=corpo):
                self.assertEqual(self.agendar(op, corpo).status_code, 400)
        self.assertEqual(self.estado(op)[1], "nenhum")

    def test_06_isolamento_entre_empresas(self):
        """Dado uma venda da empresa A / Quando B agenda ou cancela / Então recebe 404."""
        op = self.criar_oportunidade()
        self.assertEqual(self.agendar(op, {"dias": 7}, contexto["h_gestor_b"]).status_code, 404)
        r = cliente_http.delete(f"/oportunidades/{op}/agendar-reciclagem",
                                headers=contexto["h_gestor_b"])
        self.assertEqual(r.status_code, 404)

    def test_07_worker_cria_nova_oportunidade_e_preserva_a_venda(self):
        """Dado um agendamento vencido / Quando o worker roda /
        Então a venda original segue 'Fechado' (receita intacta), fica 'processado',
        e nasce uma nova oportunidade em 'Prospecção' ligada à original."""
        op = self.criar_oportunidade(valor=2500)
        self.assertEqual(self.agendar(op, {"dias": 1}).status_code, 200)
        sql("UPDATE oportunidades SET data_reciclagem_agendada = NOW() - INTERVAL '1 minute' "
            "WHERE id = %s;", (op,))

        receita_antes = cliente_http.get("/relatorios/vendas",
                                         headers=contexto["h_gestor_a"]).get_json()["receita_total"]

        criadas = worker_reciclagem.processar_reciclagens(contexto["empresa_a"])
        nova = [c for c in criadas if c["origem_id"] == op]
        self.assertEqual(len(nova), 1)
        nova_id = nova[0]["nova_id"]

        etapa, status, _ = self.estado(op)
        self.assertEqual((etapa, status), ("Fechado", "processado"))

        nova_linha = sql("""
            SELECT etapa, cliente_id, titulo, valor, oportunidade_origem_id,
                   status_reciclagem,
                   ABS(EXTRACT(EPOCH FROM NOW() - etapa_atualizada_em))
            FROM oportunidades WHERE id = %s;
        """, (nova_id,))
        self.assertEqual(nova_linha[0], "Prospecção")
        self.assertEqual(nova_linha[1], self.cliente_id)
        self.assertTrue(nova_linha[2].startswith("Reciclagem: "))
        self.assertEqual(float(nova_linha[3]), 2500.0)
        self.assertEqual(nova_linha[4], op)
        self.assertEqual(nova_linha[5], "nenhum")
        self.assertLess(nova_linha[6], 120)

        receita_depois = cliente_http.get("/relatorios/vendas",
                                          headers=contexto["h_gestor_a"]).get_json()["receita_total"]
        self.assertEqual(receita_depois, receita_antes)

        # Idempotência: uma segunda execução não reprocessa
        repetidas = worker_reciclagem.processar_reciclagens(contexto["empresa_a"])
        self.assertNotIn(op, [c["origem_id"] for c in repetidas])

    def test_08_worker_ignora_agendamento_futuro(self):
        """Dado um agendamento para daqui a 7 dias / Quando o worker roda / Então nada muda."""
        op = self.criar_oportunidade()
        self.agendar(op, {"dias": 7})
        criadas = worker_reciclagem.processar_reciclagens(contexto["empresa_a"])
        self.assertNotIn(op, [c["origem_id"] for c in criadas])
        self.assertEqual(self.estado(op)[1], "pendente")

    def test_09_mover_etapa_cancela_reciclagem_pendente(self):
        """Dado uma reciclagem pendente / Quando o card sai de 'Fechado' /
        Então o agendamento é cancelado e o worker o ignora."""
        op = self.criar_oportunidade()
        self.agendar(op, {"dias": 7})
        r = cliente_http.patch(f"/oportunidades/{op}/etapa", headers=contexto["h_gestor_a"],
                               json={"etapa": "Negociação"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.estado(op)[1], "cancelado")

        sql("UPDATE oportunidades SET data_reciclagem_agendada = NOW() - INTERVAL '1 minute' "
            "WHERE id = %s;", (op,))
        criadas = worker_reciclagem.processar_reciclagens(contexto["empresa_a"])
        self.assertNotIn(op, [c["origem_id"] for c in criadas])

    def test_10_cancelar_reciclagem(self):
        """Dado uma reciclagem pendente / Quando cancela / Então fica 'cancelado';
        cancelar de novo recebe 409."""
        op = self.criar_oportunidade()
        self.agendar(op, {"dias": 15})
        url = f"/oportunidades/{op}/agendar-reciclagem"
        self.assertEqual(cliente_http.delete(url, headers=contexto["h_gestor_a"]).status_code, 200)
        self.assertEqual(self.estado(op)[1], "cancelado")
        self.assertEqual(cliente_http.delete(url, headers=contexto["h_gestor_a"]).status_code, 409)

    def test_11_worker_executavel_pelo_terminal(self):
        """Dado o CLI em --dry-run / Então lista sem alterar e retorna 0."""
        op = self.criar_oportunidade()
        self.agendar(op, {"dias": 1})
        sql("UPDATE oportunidades SET data_reciclagem_agendada = NOW() - INTERVAL '1 minute' "
            "WHERE id = %s;", (op,))

        saida = io.StringIO()
        with contextlib.redirect_stdout(saida):
            codigo = worker_reciclagem.main(["--dry-run", "--empresa", str(contexto["empresa_a"])])

        self.assertEqual(codigo, 0)
        self.assertIn(f"oportunidade {op}", saida.getvalue())
        self.assertEqual(self.estado(op)[1], "pendente")


if __name__ == "__main__":
    unittest.main(verbosity=2)
