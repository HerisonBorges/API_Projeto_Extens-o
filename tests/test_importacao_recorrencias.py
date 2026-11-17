"""BDD (pytest): importação/exportação de planilhas e motor de recorrência.

    python3 -m pytest tests/test_importacao_recorrencias.py -v

Roda contra o banco do .env. Cria duas empresas de teste e remove tudo ao final.
O worker é SEMPRE chamado com empresa_id da empresa de teste: sem o filtro ele
processaria as regras reais do banco.
"""
import csv
import io
import uuid
import zipfile
from datetime import date, timedelta
from decimal import Decimal

import openpyxl
import pytest

import app as aplicacao
from database.conexao import get_db_connection
from database.worker_recorrencias import processar_recorrencias
from iam import gerar_hash
from importacao import COLUNAS, LIMITE_LINHAS
from recorrencia import ocorrencias_vencidas, proxima_ocorrencia

SENHA = "Gestor#Import2026"
TITULOS = [t for _, t, _ in COLUNAS]
c = aplicacao.app.test_client()


def sql(consulta, parametros=()):
    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(consulta, parametros)
            resultado = cursor.fetchall() if cursor.description else None
        conexao.commit()
    return resultado


def nova_empresa(rotulo):
    email = f"gestor.{rotulo}.{uuid.uuid4().hex[:8]}@teste.local"
    r = c.post("/auth/register", json={"nome_empresa": f"Empresa Import {rotulo} {uuid.uuid4().hex[:6]}",
                                       "nome_usuario": f"Gestor {rotulo}", "email": email, "senha": SENHA})
    assert r.status_code == 201, r.get_json()
    token = c.post("/auth/login", json={"email": email, "senha": SENHA}).get_json()["token"]
    return {"id": r.get_json()["empresa_id"], "h": {"Authorization": f"Bearer {token}"}}


@pytest.fixture(scope="module")
def empresas():
    a, b = nova_empresa("a"), nova_empresa("b")
    # Atendimento da empresa A, já com senha definitiva
    email = f"atend.{uuid.uuid4().hex[:8]}@teste.local"
    u = c.post("/usuarios", headers=a["h"], json={"nome": "Atendente", "email": email,
                                                  "perfil": "Atendimento"}).get_json()["usuario"]
    sql("UPDATE usuarios SET senha = %s, deve_trocar_senha = FALSE, senha_temporaria_expira_em = NULL "
        "WHERE id = %s;", (gerar_hash(SENHA), u["id"]))
    token = c.post("/auth/login", json={"email": email, "senha": SENHA}).get_json()["token"]
    a["atendimento"] = {"Authorization": f"Bearer {token}"}
    yield {"a": a, "b": b}
    for empresa in (a, b):
        for tabela in ("importacoes", "recorrencia_execucoes", "recorrencias", "auditoria_usuarios",
                       "interacoes", "tarefas", "oportunidades", "clientes", "configuracoes", "usuarios"):
            sql(f"DELETE FROM {tabela} WHERE empresa_id = %s;", (empresa["id"],))
        sql("DELETE FROM empresas WHERE id = %s;", (empresa["id"],))


def gerar_cpf(base9):
    """CPF válido a partir de 9 dígitos (para testes)."""
    def dv(nums, pesos):
        resto = sum(n * p for n, p in zip(nums, pesos)) % 11
        return 0 if resto < 2 else 11 - resto
    n = [int(x) for x in base9]
    d1 = dv(n, range(10, 1, -1))
    d2 = dv(n + [d1], range(11, 1, -1))
    return f"{base9}{d1}{d2}"


def cpf_unico():
    return gerar_cpf(str(uuid.uuid4().int)[:9])


def planilha_csv(linhas, separador=";", codificacao="utf-8-sig", cabecalho=TITULOS):
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=separador, lineterminator="\r\n")
    escritor.writerow(cabecalho)
    for linha in linhas:
        escritor.writerow(linha + [""] * (len(cabecalho) - len(linha)))
    return saida.getvalue().encode(codificacao)


def planilha_xlsx(linhas):
    livro = openpyxl.Workbook()
    folha = livro.active
    folha.title = "Clientes"
    folha.append(TITULOS)
    for linha in linhas:
        folha.append(linha)
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()


def enviar(h, conteudo, nome="clientes.csv", simular=False):
    return c.post(f"/clientes/importar{'?simular=1' if simular else ''}", headers=h,
                  data={"arquivo": (io.BytesIO(conteudo), nome)}, content_type="multipart/form-data")


def contar_clientes(empresa_id):
    return sql("SELECT COUNT(*) FROM clientes WHERE empresa_id = %s;", (empresa_id,))[0][0]


def hoje_empresa():
    return sql("SELECT (NOW() AT TIME ZONE 'America/Sao_Paulo')::date;")[0][0]


# ---- Modelo oficial ------------------------------------------------------------

class TestModelo:

    def test_xlsx_tem_colunas_instrucoes_e_listas(self, empresas):
        r = c.get("/clientes/modelo?formato=xlsx", headers=empresas["a"]["atendimento"])
        assert r.status_code == 200
        assert 'filename="sandro-crm-modelo-clientes.xlsx"' in r.headers["Content-Disposition"]
        livro = openpyxl.load_workbook(io.BytesIO(r.data))
        assert livro.sheetnames == ["Clientes", "Instruções"]
        assert [cel.value for cel in livro["Clientes"][1]] == TITULOS
        assert livro["Clientes"].max_row == 1  # sem linha de exemplo que seria importada por engano
        assert len(livro["Clientes"].data_validations.dataValidation) == 3

    def test_csv_abre_no_excel_em_portugues(self, empresas):
        r = c.get("/clientes/modelo?formato=csv", headers=empresas["a"]["h"])
        assert r.status_code == 200
        assert r.data.startswith("\ufeff".encode("utf-8"))  # BOM: acentos certos no Excel
        assert r.data.decode("utf-8-sig").split("\r\n")[0] == ";".join(TITULOS)

    def test_formato_invalido(self, empresas):
        assert c.get("/clientes/modelo?formato=exe", headers=empresas["a"]["h"]).status_code == 400


# ---- Arquivos maliciosos ou inválidos -----------------------------------------

class TestArquivosMaliciosos:

    @pytest.mark.parametrize("celula, coluna", [
        ("=HYPERLINK(\"http://x.example\",\"clique\")", 0),
        ("+cmd|' /C calc'!A0", 0),
        ("-2+3", 0),
        ("@SUM(1+1)", 0),
    ])
    def test_formula_injection_e_recusada_com_linha_e_coluna(self, empresas, celula, coluna):
        a = empresas["a"]
        antes = contar_clientes(a["id"])
        linha = ["Cliente OK"] + [""] * 10
        linha[coluna] = celula
        r = enviar(a["h"], planilha_csv([["Cliente Bom"], linha]))
        assert r.status_code == 422
        corpo = r.get_json()
        assert corpo["valido"] is False
        assert corpo["erros"][0]["linha"] == 3
        assert corpo["erros"][0]["coluna"] == TITULOS[coluna]
        assert "fórmula" in corpo["erros"][0]["mensagem"]
        assert contar_clientes(a["id"]) == antes  # nem a linha boa entrou

    def test_formula_nas_notas_da_recorrencia(self, empresas):
        r = enviar(empresas["a"]["h"], planilha_csv([["Cliente", "", "", "", "", "lembrete", "mensal", "5",
                                                      "Fechamento", "", "=1+1"]]))
        assert r.status_code == 422
        assert r.get_json()["erros"][0]["coluna"] == "Notas de compra"

    def test_xss_e_recusado(self, empresas):
        r = enviar(empresas["a"]["h"], planilha_csv([["<script>alert(1)</script>"],
                                                     ["Ana <img src=x onerror=alert(1)>"]]))
        assert r.status_code == 422
        erros = r.get_json()["erros"]
        assert [e["linha"] for e in erros] == [2, 3]
        assert all("HTML" in e["mensagem"] for e in erros)

    def test_caractere_de_controle(self, empresas):
        r = enviar(empresas["a"]["h"], planilha_csv([["Cliente\x07Sino"]]))
        assert r.status_code == 422

    def test_extensao_nao_permitida(self, empresas):
        r = enviar(empresas["a"]["h"], b"MZ\x90\x00binario", nome="planilha.exe")
        assert r.status_code == 400
        assert ".xlsx ou .csv" in r.get_json()["erro"]

    def test_binario_disfarcado_de_csv(self, empresas):
        r = enviar(empresas["a"]["h"], b"MZ\x90\x00\x03\x00\x00\x00", nome="clientes.csv")
        assert r.status_code == 400

    def test_binario_disfarcado_de_xlsx(self, empresas):
        r = enviar(empresas["a"]["h"], b"%PDF-1.7 nao sou planilha", nome="clientes.xlsx")
        assert r.status_code == 400
        assert "não é um .xlsx" in r.get_json()["erro"]

    def test_xlsm_com_macro_e_recusado(self, empresas):
        r = enviar(empresas["a"]["h"], planilha_xlsx([["Cliente"]]), nome="clientes.xlsm")
        assert r.status_code == 400
        assert "macros" in r.get_json()["erro"]

    def test_xlsx_com_vba_embutido_e_recusado(self, empresas):
        original = zipfile.ZipFile(io.BytesIO(planilha_xlsx([["Cliente"]])))
        saida = io.BytesIO()
        with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as novo:
            for item in original.infolist():
                novo.writestr(item, original.read(item.filename))
            novo.writestr("xl/vbaProject.bin", b"\x00" * 64)
        r = enviar(empresas["a"]["h"], saida.getvalue(), nome="clientes.xlsx")
        assert r.status_code == 400
        assert "macros" in r.get_json()["erro"]

    def test_xlsx_com_entidades_xml_billion_laughs(self, empresas):
        """XXE / billion laughs: o defusedxml recusa DTD com entidades."""
        original = zipfile.ZipFile(io.BytesIO(planilha_xlsx([["Cliente"]])))
        saida = io.BytesIO()
        ataque = ('<?xml version="1.0"?><!DOCTYPE bomba [<!ENTITY a "aaaaaaaaaa">'
                  '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;"><!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]>')
        with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as novo:
            for item in original.infolist():
                conteudo = original.read(item.filename)
                if item.filename == "xl/workbook.xml":
                    texto = conteudo.decode("utf-8")
                    if texto.startswith("<?xml"):
                        texto = texto[texto.index("?>") + 2:]
                    texto = ataque + texto.replace('name="Clientes"', 'name="&c;"')
                    conteudo = texto.encode("utf-8")
                novo.writestr(item, conteudo)
        r = enviar(empresas["a"]["h"], saida.getvalue(), nome="clientes.xlsx")
        assert r.status_code == 400
        assert "não permitido" in r.get_json()["erro"]

    def test_xlsx_com_xxe_em_utf16(self, empresas):
        """XXE (ler arquivo do servidor) escondido em UTF-16 para fugir de busca simples."""
        original = zipfile.ZipFile(io.BytesIO(planilha_xlsx([["Cliente"]])))
        saida = io.BytesIO()
        with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as novo:
            for item in original.infolist():
                conteudo = original.read(item.filename)
                if item.filename == "xl/sharedStrings.xml" or item.filename == "xl/workbook.xml":
                    texto = conteudo.decode("utf-8")
                    if texto.startswith("<?xml"):
                        texto = texto[texto.index("?>") + 2:]
                    texto = ('<?xml version="1.0" encoding="UTF-16"?>'
                             '<!DOCTYPE x [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>' + texto)
                    conteudo = texto.encode("utf-16-le")
                novo.writestr(item, conteudo)
        r = enviar(empresas["a"]["h"], saida.getvalue(), nome="clientes.xlsx")
        assert r.status_code == 400
        assert "não permitido" in r.get_json()["erro"]

    def test_zip_bomb(self, empresas):
        saida = io.BytesIO()
        with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as bomba:
            bomba.writestr("[Content_Types].xml", "<Types/>")
            bomba.writestr("xl/worksheets/sheet1.xml", b"0" * (30 * 1024 * 1024))
        assert len(saida.getvalue()) < 1024 * 1024  # 30 MB que viram ~30 KB
        r = enviar(empresas["a"]["h"], saida.getvalue(), nome="clientes.xlsx")
        assert r.status_code == 400

    def test_arquivo_acima_de_1mb(self, empresas):
        r = enviar(empresas["a"]["h"], b"Nome do cliente *\n" + b"a" * (1024 * 1024 + 10))
        assert r.status_code == 413

    def test_linhas_demais(self, empresas):
        r = enviar(empresas["a"]["h"], planilha_csv([[f"C{i}"] for i in range(LIMITE_LINHAS + 5)], separador=","))
        assert r.status_code == 400
        assert str(LIMITE_LINHAS) in r.get_json()["erro"]

    def test_cabecalho_errado(self, empresas):
        r = enviar(empresas["a"]["h"], planilha_csv([["x"]], cabecalho=["Coluna A", "Coluna B"]))
        assert r.status_code == 400
        assert "Nome do cliente" in r.get_json()["erro"]

    def test_sem_arquivo(self, empresas):
        r = c.post("/clientes/importar", headers=empresas["a"]["h"], data={}, content_type="multipart/form-data")
        assert r.status_code == 400


# ---- Importação válida, atomicidade e prévia ---------------------------------

class TestImportacao:

    def test_uma_linha_ruim_bloqueia_o_arquivo_inteiro(self, empresas):
        a = empresas["a"]
        antes = contar_clientes(a["id"])
        r = enviar(a["h"], planilha_csv([
            ["Bom 1"], ["Bom 2"], ["Bom 3"],
            ["Ruim", "123.456.789-00", "email-invalido", "12", "VIP"],
        ]))
        assert r.status_code == 422
        corpo = r.get_json()
        colunas = {e["coluna"] for e in corpo["erros"]}
        assert colunas == {"CPF/CNPJ", "E-mail", "Telefone", "Status"}
        assert all(e["linha"] == 5 for e in corpo["erros"])
        assert "Nada foi importado" in corpo["erro"]
        assert contar_clientes(a["id"]) == antes

    def test_simular_mostra_previa_e_nao_grava(self, empresas):
        a = empresas["a"]
        antes = contar_clientes(a["id"])
        linhas = [[f"Prévia {i}", cpf_unico(), f"p{i}@ex.com"] for i in range(8)]
        r = enviar(a["h"], planilha_csv(linhas), simular=True)
        assert r.status_code == 200
        corpo = r.get_json()
        assert corpo["valido"] is True and corpo["clientes"] == 8
        assert len(corpo["previa"]) == 5
        assert corpo["previa"][0]["nome"] == "Prévia 0" and corpo["previa"][0]["linha"] == 2
        assert contar_clientes(a["id"]) == antes

    def test_csv_do_excel_em_cp1252_com_valor_brasileiro(self, empresas):
        a = empresas["a"]
        doc = cpf_unico()
        r = enviar(a["h"], planilha_csv([
            ["Padaria São João", f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}", "PADARIA@EX.COM",
             "+55 (11) 3000-0003", "cliente", "oportunidade", "semanal", "segunda-feira",
             "Compra semanal de pães", "R$ 1.250,90", "Entregar até 8h"],
            # Mesmo CPF: segunda recorrência do mesmo cliente
            ["Padaria São João", doc, "padaria@ex.com", "+55 (11) 3000-0003", "Cliente",
             "lembrete", "mensal", "31", "Fechamento do mês"],
        ], codificacao="cp1252"))
        assert r.status_code == 201, r.get_json()
        assert r.get_json()["clientes_criados"] == 1
        assert r.get_json()["recorrencias_criadas"] == 2

        cliente = sql("SELECT id, nome, documento, email, status FROM clientes WHERE empresa_id = %s AND documento = %s;",
                      (a["id"], doc))[0]
        assert cliente[1:] == ("Padaria São João", doc, "padaria@ex.com", "Cliente")
        regras = sql("SELECT tipo, frequencia, dia_semana, dia_mes, valor, proxima_execucao FROM recorrencias "
                     "WHERE cliente_id = %s ORDER BY id;", (cliente[0],))
        hoje = hoje_empresa()
        assert regras[0][:5] == ("oportunidade", "semanal", 1, None, Decimal("1250.90"))
        assert regras[0][5] == proxima_ocorrencia("semanal", 1, None, hoje)
        assert regras[1][:5] == ("lembrete", "mensal", None, 31, None)
        registro = sql("SELECT formato, linhas, clientes_criados, recorrencias_criadas, length(sha256) "
                       "FROM importacoes WHERE empresa_id = %s ORDER BY id DESC LIMIT 1;", (a["id"],))[0]
        assert registro == ("csv", 2, 1, 2, 64)

    def test_xlsx_com_cpf_numerico_sem_zero_a_esquerda(self, empresas):
        a = empresas["a"]
        doc = gerar_cpf("0" + str(uuid.uuid4().int)[:8])
        r = enviar(a["h"], planilha_xlsx([["Cliente XLSX", int(doc), None, None, None,
                                            "lembrete", "mensal", 5, "Cobrança"]]), nome="lote.xlsx")
        assert r.status_code == 201, r.get_json()
        assert sql("SELECT documento FROM clientes WHERE empresa_id = %s AND nome = 'Cliente XLSX';",
                   (a["id"],))[0][0] == doc

    def test_cpf_repetido_na_empresa_e_recusado(self, empresas):
        a = empresas["a"]
        doc = cpf_unico()
        assert enviar(a["h"], planilha_csv([["Primeira vez", doc]])).status_code == 201
        r = enviar(a["h"], planilha_csv([["Segunda vez", doc]]))
        assert r.status_code == 422
        assert "Já existe um cliente com este CPF/CNPJ" in r.get_json()["erros"][0]["mensagem"]

    def test_cnpj_alfanumerico_aceito(self, empresas):
        r = enviar(empresas["a"]["h"], planilha_csv([["Empresa Nova Ltda", "12.ABC.345/01DE-35"]]))
        assert r.status_code in (201, 422)  # 422 só se outro teste já usou este CNPJ fixo
        if r.status_code == 422:
            assert "Já existe" in r.get_json()["erros"][0]["mensagem"]


# ---- Isolamento por empresa e perfil ------------------------------------------

class TestIsolamento:

    def test_atendimento_nao_importa_nem_exporta(self, empresas):
        h = empresas["a"]["atendimento"]
        assert enviar(h, planilha_csv([["X"]])).status_code == 403
        assert c.get("/clientes/exportar", headers=h).status_code == 403

    def test_mesmo_cpf_em_outra_empresa_e_independente(self, empresas):
        a, b = empresas["a"], empresas["b"]
        doc = cpf_unico()
        assert enviar(a["h"], planilha_csv([["Cliente da A", doc, "", "", "", "lembrete", "semanal", "sexta"]])).status_code == 201
        assert enviar(b["h"], planilha_csv([["Cliente da B", doc]])).status_code == 201
        assert sql("SELECT empresa_id FROM clientes WHERE nome = 'Cliente da B' AND documento = %s;",
                   (doc,))[0][0] == b["id"]
        nomes_b = [cl["nome"] for cl in c.get("/clientes", headers=b["h"]).get_json()]
        assert "Cliente da A" not in nomes_b

    def test_regra_de_outra_empresa_responde_404(self, empresas):
        a, b = empresas["a"], empresas["b"]
        regra_a = c.get("/recorrencias", headers=a["h"]).get_json()[0]
        assert all(r["empresa_id"] == b["id"] for r in c.get("/recorrencias", headers=b["h"]).get_json())
        corpo = {"tipo": "lembrete", "titulo": "Invasão", "frequencia": "semanal", "dia_semana": 1}
        assert c.put(f"/recorrencias/{regra_a['id']}", headers=b["h"], json=corpo).status_code == 404
        assert c.patch(f"/recorrencias/{regra_a['id']}/ativo", headers=b["h"], json={"ativo": False}).status_code == 404
        assert c.delete(f"/recorrencias/{regra_a['id']}", headers=b["h"]).status_code == 404
        cliente_a = regra_a["cliente_id"]
        assert c.post("/recorrencias", headers=b["h"], json={**corpo, "cliente_id": cliente_a}).status_code == 404

    def test_exportacao_so_traz_a_propria_empresa_e_neutraliza_formulas(self, empresas):
        a, b = empresas["a"], empresas["b"]
        # Dado gravado por outro caminho (ex.: antes desta versão): a saída precisa neutralizar
        sql("INSERT INTO clientes (empresa_id, nome, status) VALUES (%s, '=1+1', 'Lead');", (a["id"],))
        r = c.get("/clientes/exportar?formato=csv", headers=a["h"])
        assert r.status_code == 200
        texto = r.data.decode("utf-8-sig")
        assert "'=1+1" in texto
        assert "Cliente da B" not in texto
        xlsx = c.get("/clientes/exportar?formato=xlsx", headers=a["h"])
        folha = openpyxl.load_workbook(io.BytesIO(xlsx.data))["Clientes"]
        valores = [cel.value for linha in folha.iter_rows(min_row=2) for cel in linha]
        assert "'=1+1" in valores and "=1+1" not in valores
        exportado_b = c.get("/clientes/exportar?formato=csv", headers=b["h"]).data.decode("utf-8-sig")
        assert "=1+1" not in exportado_b


# ---- Motor de recorrência ------------------------------------------------------

class TestCalculoDeDatas:

    def test_todo_dia_31_vira_ultimo_dia_do_mes(self):
        assert proxima_ocorrencia("mensal", None, 31, date(2027, 2, 1)) == date(2027, 2, 28)
        assert proxima_ocorrencia("mensal", None, 31, date(2028, 2, 1)) == date(2028, 2, 29)  # bissexto
        assert proxima_ocorrencia("mensal", None, 31, date(2026, 4, 30), incluir_o_dia=False) == date(2026, 5, 31)

    def test_todo_dia_5(self):
        assert proxima_ocorrencia("mensal", None, 5, date(2026, 11, 5)) == date(2026, 11, 5)
        assert proxima_ocorrencia("mensal", None, 5, date(2026, 11, 6)) == date(2026, 12, 5)
        assert proxima_ocorrencia("mensal", None, 5, date(2026, 12, 6)) == date(2027, 1, 5)

    def test_toda_segunda(self):
        # 16/11/2026 é segunda-feira
        assert proxima_ocorrencia("semanal", 1, None, date(2026, 11, 16)) == date(2026, 11, 16)
        assert proxima_ocorrencia("semanal", 1, None, date(2026, 11, 16), incluir_o_dia=False) == date(2026, 11, 23)
        assert proxima_ocorrencia("semanal", 7, None, date(2026, 11, 16)) == date(2026, 11, 22)

    def test_datas_perdidas_com_limite(self):
        regra = {"frequencia": "semanal", "dia_semana": 1, "dia_mes": None, "proxima_execucao": date(2026, 1, 5)}
        datas, proxima, puladas = ocorrencias_vencidas(regra, date(2026, 11, 16))
        assert len(datas) == 12 and puladas == 34
        assert datas[-1] == date(2026, 11, 16) and proxima == date(2026, 11, 23)


class TestWorker:

    @pytest.fixture()
    def cliente(self, empresas):
        r = c.post("/clientes", headers=empresas["a"]["h"], json={"nome": f"Recorrente {uuid.uuid4().hex[:5]}"})
        return r.get_json()["cliente_id"]

    def criar_regra(self, empresas, cliente, **campos):
        corpo = {"cliente_id": cliente, "tipo": "lembrete", "titulo": "Fechamento", "frequencia": "mensal",
                 "dia_mes": 5, **campos}
        r = c.post("/recorrencias", headers=empresas["a"]["h"], json=corpo)
        assert r.status_code == 201, r.get_json()
        return r.get_json()["recorrencia"]

    def test_fechamento_todo_dia_5_gera_follow_up_uma_unica_vez(self, empresas, cliente):
        a = empresas["a"]
        regra = self.criar_regra(empresas, cliente, notas="Conferir notas fiscais")
        sql("UPDATE recorrencias SET proxima_execucao = '2026-11-05' WHERE id = %s;", (regra["id"],))

        resumo = processar_recorrencias(empresa_id=a["id"], hoje=date(2026, 11, 5))
        assert resumo["tarefas"] >= 1
        tarefas = sql("SELECT titulo, descricao, data_vencimento, concluida FROM tarefas WHERE recorrencia_id = %s;",
                      (regra["id"],))
        assert tarefas == [("Fechamento", "Conferir notas fiscais", date(2026, 11, 5), False)]
        assert sql("SELECT proxima_execucao FROM recorrencias WHERE id = %s;", (regra["id"],))[0][0] == date(2026, 12, 5)

        # Reprocessar a mesma data (ex.: alguém voltou a data à mão) não duplica
        sql("UPDATE recorrencias SET proxima_execucao = '2026-11-05' WHERE id = %s;", (regra["id"],))
        processar_recorrencias(empresa_id=a["id"], hoje=date(2026, 11, 5))
        assert sql("SELECT COUNT(*) FROM tarefas WHERE recorrencia_id = %s;", (regra["id"],))[0][0] == 1

    def test_oportunidade_semanal_entra_no_funil(self, empresas, cliente):
        a = empresas["a"]
        regra = self.criar_regra(empresas, cliente, tipo="oportunidade", titulo="Compra semanal",
                                 valor=350.0, frequencia="semanal", dia_semana=1)
        sql("UPDATE recorrencias SET proxima_execucao = '2026-11-16' WHERE id = %s;", (regra["id"],))
        processar_recorrencias(empresa_id=a["id"], hoje=date(2026, 11, 16))
        op = sql("SELECT titulo, valor, etapa, cliente_id FROM oportunidades WHERE recorrencia_id = %s;", (regra["id"],))
        assert op == [("Compra semanal · 16/11/2026", 350.0, "Prospecção", cliente)]

    def test_worker_parado_gera_cada_mes_perdido(self, empresas, cliente):
        a = empresas["a"]
        regra = self.criar_regra(empresas, cliente)
        sql("UPDATE recorrencias SET proxima_execucao = '2026-08-05' WHERE id = %s;", (regra["id"],))
        processar_recorrencias(empresa_id=a["id"], hoje=date(2026, 11, 5))
        datas = [d for (d,) in sql("SELECT data_vencimento FROM tarefas WHERE recorrencia_id = %s ORDER BY 1;",
                                   (regra["id"],))]
        assert datas == [date(2026, 8, 5), date(2026, 9, 5), date(2026, 10, 5), date(2026, 11, 5)]

    def test_pausada_nao_gera_e_retomar_conta_a_partir_de_hoje(self, empresas, cliente):
        a = empresas["a"]
        regra = self.criar_regra(empresas, cliente)
        sql("UPDATE recorrencias SET proxima_execucao = '2026-10-05' WHERE id = %s;", (regra["id"],))
        assert c.patch(f"/recorrencias/{regra['id']}/ativo", headers=a["h"], json={"ativo": False}).status_code == 200
        processar_recorrencias(empresa_id=a["id"], hoje=date(2026, 11, 5))
        assert sql("SELECT COUNT(*) FROM tarefas WHERE recorrencia_id = %s;", (regra["id"],))[0][0] == 0

        retomada = c.patch(f"/recorrencias/{regra['id']}/ativo", headers=a["h"], json={"ativo": True}).get_json()
        assert retomada["recorrencia"]["proxima_execucao"] >= hoje_empresa().isoformat()

    def test_cliente_inativo_avanca_sem_gerar(self, empresas, cliente):
        a = empresas["a"]
        regra = self.criar_regra(empresas, cliente)
        c.put(f"/clientes/{cliente}", headers=a["h"], json={"status": "Inativo"})
        sql("UPDATE recorrencias SET proxima_execucao = '2026-11-05' WHERE id = %s;", (regra["id"],))
        processar_recorrencias(empresa_id=a["id"], hoje=date(2026, 11, 5))
        assert sql("SELECT COUNT(*) FROM tarefas WHERE recorrencia_id = %s;", (regra["id"],))[0][0] == 0
        assert sql("SELECT proxima_execucao FROM recorrencias WHERE id = %s;", (regra["id"],))[0][0] == date(2026, 12, 5)

    def test_worker_respeita_o_filtro_de_empresa(self, empresas):
        a, b = empresas["a"], empresas["b"]
        cliente_b = c.post("/clientes", headers=b["h"], json={"nome": "Cliente B worker"}).get_json()["cliente_id"]
        regra_b = c.post("/recorrencias", headers=b["h"], json={
            "cliente_id": cliente_b, "tipo": "lembrete", "titulo": "Da B", "frequencia": "mensal", "dia_mes": 5,
        }).get_json()["recorrencia"]
        sql("UPDATE recorrencias SET proxima_execucao = '2026-11-05' WHERE id = %s;", (regra_b["id"],))
        processar_recorrencias(empresa_id=a["id"], hoje=date(2026, 11, 5))
        assert sql("SELECT COUNT(*) FROM tarefas WHERE recorrencia_id = %s;", (regra_b["id"],))[0][0] == 0

    def test_simulacao_nao_altera_nada(self, empresas, cliente):
        a = empresas["a"]
        regra = self.criar_regra(empresas, cliente)
        sql("UPDATE recorrencias SET proxima_execucao = '2026-11-05' WHERE id = %s;", (regra["id"],))
        resumo = processar_recorrencias(empresa_id=a["id"], hoje=date(2026, 11, 5), simular=True)
        assert resumo["tarefas"] >= 1
        assert sql("SELECT COUNT(*) FROM tarefas WHERE recorrencia_id = %s;", (regra["id"],))[0][0] == 0
        assert sql("SELECT proxima_execucao FROM recorrencias WHERE id = %s;", (regra["id"],))[0][0] == date(2026, 11, 5)


class TestApiRecorrencias:

    def test_validacoes(self, empresas):
        h = empresas["a"]["h"]
        cliente = c.post("/clientes", headers=h, json={"nome": "Validação"}).get_json()["cliente_id"]
        base = {"cliente_id": cliente, "tipo": "lembrete", "titulo": "X", "frequencia": "mensal", "dia_mes": 5}
        assert c.post("/recorrencias", headers=h, json={**base, "dia_mes": 32}).status_code == 400
        assert c.post("/recorrencias", headers=h, json={**base, "frequencia": "diaria"}).status_code == 400
        assert c.post("/recorrencias", headers=h, json={**base, "frequencia": "semanal", "dia_semana": 0}).status_code == 400
        assert c.post("/recorrencias", headers=h, json={**base, "tipo": "x"}).status_code == 400
        r = c.post("/recorrencias", headers=h, json=base)
        assert r.status_code == 201
        assert r.get_json()["recorrencia"]["descricao"] == "Todo dia 5"

    def test_atendimento_cria_mas_nao_exclui(self, empresas):
        a = empresas["a"]
        cliente = c.post("/clientes", headers=a["h"], json={"nome": "Atend"}).get_json()["cliente_id"]
        r = c.post("/recorrencias", headers=a["atendimento"], json={
            "cliente_id": cliente, "tipo": "lembrete", "titulo": "Ligar", "frequencia": "semanal", "dia_semana": 3})
        assert r.status_code == 201
        assert c.delete(f"/recorrencias/{r.get_json()['recorrencia']['id']}", headers=a["atendimento"]).status_code == 403
        assert c.delete(f"/recorrencias/{r.get_json()['recorrencia']['id']}", headers=a["h"]).status_code == 200

    def test_nova_oportunidade_com_repeticao_e_atomica(self, empresas):
        a = empresas["a"]
        cliente = c.post("/clientes", headers=a["h"], json={"nome": "Op recorrente"}).get_json()["cliente_id"]
        r = c.post("/oportunidades", headers=a["h"], json={
            "cliente_id": cliente, "titulo": "Reposição", "valor": 99.9,
            "recorrencia": {"frequencia": "semanal", "dia_semana": hoje_empresa().isoweekday()}})
        assert r.status_code == 201, r.get_json()
        regra = sql("SELECT tipo, titulo, valor, proxima_execucao FROM recorrencias WHERE id = %s;",
                    (r.get_json()["recorrencia_id"],))[0]
        # A de hoje é a que acabou de ser criada: a próxima é daqui a 7 dias
        assert regra == ("oportunidade", "Reposição", Decimal("99.90"), hoje_empresa() + timedelta(days=7))
        assert sql("SELECT recorrencia_id FROM oportunidades WHERE id = %s;",
                   (r.get_json()["oportunidade_id"],))[0][0] == r.get_json()["recorrencia_id"]
        # Regra inválida: nem a oportunidade é criada
        antes = sql("SELECT COUNT(*) FROM oportunidades WHERE empresa_id = %s;", (a["id"],))[0][0]
        ruim = c.post("/oportunidades", headers=a["h"], json={
            "cliente_id": cliente, "titulo": "Não deve entrar", "recorrencia": {"frequencia": "anual"}})
        assert ruim.status_code == 400
        assert sql("SELECT COUNT(*) FROM oportunidades WHERE empresa_id = %s;", (a["id"],))[0][0] == antes

    def test_cadastro_manual_aceita_cnpj_e_recusa_duplicado(self, empresas):
        h = empresas["a"]["h"]
        doc = cpf_unico()
        r = c.post("/clientes", headers=h, json={"nome": "Manual", "documento": doc})
        assert r.status_code == 201
        assert c.get(f"/clientes/{r.get_json()['cliente_id']}", headers=h).get_json()["documento"] == doc
        assert c.post("/clientes", headers=h, json={"nome": "Manual 2", "documento": doc}).status_code == 409
        assert c.post("/clientes", headers=h, json={"nome": "Manual 3", "documento": "123"}).status_code == 400
