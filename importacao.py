"""Leitura e validação de planilhas de clientes (CSV e XLSX).

Princípios:
  - O arquivo nunca é salvo em disco nem executado: é lido da memória.
  - Tudo ou nada: qualquer linha inválida impede a importação inteira, e a
    resposta diz a linha, a coluna e o motivo.
  - Defesa contra:
      * CSV/Formula Injection: célula começando com = + - @ é recusada na
        entrada e neutralizada na saída (exportação);
      * XSS armazenado: marcação HTML (<tag) é recusada; o front ainda escapa tudo;
      * XML malicioso no .xlsx (XXE, "billion laughs"): openpyxl usa defusedxml;
        sem ele, .xlsx é recusado;
      * zip bomb: limite de tamanho descompactado e de taxa de compressão;
      * macros: .xlsm e .xlsx com vbaProject.bin são recusados;
      * arquivos enormes: limite de bytes e de linhas.
"""
import csv
import hashlib
import io
import re
import unicodedata
import zipfile
from datetime import date, datetime

from documento import normalizar_documento
from iam import normalizar_email, validar_email
from recorrencia import FREQUENCIAS, TIPOS, validar_recorrencia

LIMITE_BYTES = 1024 * 1024          # igual ao MAX_CONTENT_LENGTH da API
LIMITE_LINHAS = 2000                # linhas de dados por arquivo
LIMITE_COLUNAS = 30
LIMITE_DESCOMPACTADO = 25 * 1024 * 1024
LIMITE_TAXA_COMPRESSAO = 100        # zip bomb típico passa de 1000:1
LIMITE_ERROS_LISTADOS = 100
LINHAS_PREVIA = 5

STATUS_VALIDOS = ("Lead", "Cliente", "Inativo")
_TELEFONE = re.compile(r"^\+?[0-9()\-.\s]{8,30}$")
_HTML = re.compile(r"<\s*[A-Za-z!/?]")
_CONTROLE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
INICIO_FORMULA = ("=", "+", "-", "@")

# (chave interna, título da coluna no modelo, ajuda exibida na aba Instruções)
COLUNAS = [
    ("nome", "Nome do cliente *", "Obrigatório. Até 150 caracteres."),
    ("documento", "CPF/CNPJ", "Opcional. Com ou sem pontuação; aceita o CNPJ alfanumérico. "
                              "Repita o mesmo CPF/CNPJ em várias linhas para dar várias recorrências ao cliente."),
    ("email", "E-mail", "Opcional."),
    ("telefone", "Telefone", "Opcional. De 8 a 30 dígitos; pode começar com +55."),
    ("status", "Status", "Lead, Cliente ou Inativo. Vazio = Lead."),
    ("rec_tipo", "Recorrência: tipo", "Vazio = sem recorrência. 'lembrete' cria um follow-up; "
                                      "'oportunidade' cria um card no funil."),
    ("rec_frequencia", "Recorrência: frequência", "semanal ou mensal."),
    ("rec_dia", "Recorrência: dia", "Semanal: segunda a domingo. Mensal: 1 a 31 "
                                    "(31 = último dia nos meses mais curtos)."),
    ("rec_titulo", "Recorrência: título", "Ex.: Compra semanal de pães. Vazio = 'Compra recorrente'."),
    ("rec_valor", "Valor (R$)", "Só para oportunidade. Ex.: 1.250,90"),
    ("rec_notas", "Notas de compra", "Opcional. Até 2000 caracteres."),
]
TITULOS = {chave: titulo for chave, titulo, _ in COLUNAS}
CAMPOS_RECORRENCIA = ("rec_tipo", "rec_frequencia", "rec_dia", "rec_titulo", "rec_valor", "rec_notas")

DIAS_SEMANA_TEXTO = {
    "segunda": 1, "seg": 1, "segunda-feira": 1, "terca": 2, "ter": 2, "terca-feira": 2,
    "quarta": 3, "qua": 3, "quarta-feira": 3, "quinta": 4, "qui": 4, "quinta-feira": 4,
    "sexta": 5, "sex": 5, "sexta-feira": 5, "sabado": 6, "sab": 6, "domingo": 7, "dom": 7,
}


class ArquivoInvalido(Exception):
    """Problema no arquivo inteiro (formato, tamanho, estrutura)."""


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _chave_cabecalho(texto):
    texto = _sem_acento(str(texto)).lower().replace("*", "")
    return re.sub(r"[\s:_]+", " ", texto).strip()


# Títulos aceitos para cada coluna (o do modelo e variações comuns)
APELIDOS = {
    "nome": ["nome do cliente", "nome", "cliente", "razao social"],
    "documento": ["cpf/cnpj", "cpf", "cnpj", "documento", "cpf cnpj"],
    "email": ["e-mail", "email"],
    "telefone": ["telefone", "celular", "whatsapp", "fone"],
    "status": ["status", "situacao"],
    "rec_tipo": ["recorrencia tipo", "tipo de recorrencia", "tipo"],
    "rec_frequencia": ["recorrencia frequencia", "frequencia", "frequencia de compra"],
    "rec_dia": ["recorrencia dia", "dia", "dia de vencimento", "data de vencimento"],
    "rec_titulo": ["recorrencia titulo", "titulo"],
    "rec_valor": ["valor (r$)", "valor", "valor r$"],
    "rec_notas": ["notas de compra", "notas", "observacoes"],
}
_CABECALHOS = {_chave_cabecalho(a): chave for chave, apelidos in APELIDOS.items() for a in apelidos}


def sha256(conteudo):
    return hashlib.sha256(conteudo).hexdigest()


def nome_seguro(nome):
    """Nome do arquivo só para registro: sem caminho e sem caracteres estranhos."""
    base = re.split(r"[\\/]", nome or "")[-1]
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", _sem_acento(base))[:120]
    return base or "arquivo"


# ---- Leitura do arquivo ------------------------------------------------------

def ler_planilha(nome_arquivo, conteudo):
    """Retorna (formato, linhas) com linhas = [(numero_da_linha, [valores...]), ...].

    numero_da_linha é o da planilha (1 = primeira linha), para a pessoa achar o erro.
    """
    if not conteudo:
        raise ArquivoInvalido("O arquivo está vazio.")
    if len(conteudo) > LIMITE_BYTES:
        raise ArquivoInvalido("O arquivo passa de 1 MB. Divida em arquivos menores.")

    extensao = (nome_arquivo or "").lower().rsplit(".", 1)[-1] if "." in (nome_arquivo or "") else ""
    if extensao == "csv":
        return "csv", _ler_csv(conteudo)
    if extensao == "xlsx":
        return "xlsx", _ler_xlsx(conteudo)
    if extensao in ("xlsm", "xls", "xlsb"):
        raise ArquivoInvalido("Formato não aceito. Salve como .xlsx (sem macros) ou .csv.")
    raise ArquivoInvalido("Envie um arquivo .xlsx ou .csv.")


def _ler_csv(conteudo):
    if b"\x00" in conteudo:
        raise ArquivoInvalido("O arquivo não é um CSV de texto.")
    for codificacao in ("utf-8-sig", "cp1252"):  # cp1252 = CSV salvo pelo Excel em português
        try:
            texto = conteudo.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ArquivoInvalido("Não foi possível ler o texto do CSV. Salve como CSV UTF-8.")

    primeira = texto.split("\n", 1)[0]
    separador = max((";", ",", "\t"), key=primeira.count)
    linhas = []
    try:
        for indice, valores in enumerate(csv.reader(io.StringIO(texto, newline=""), delimiter=separador), start=1):
            if len(linhas) > LIMITE_LINHAS + 1:
                raise ArquivoInvalido(f"O arquivo passa de {LIMITE_LINHAS} linhas. Divida em arquivos menores.")
            linhas.append((indice, valores[:LIMITE_COLUNAS]))
    except csv.Error as erro:
        raise ArquivoInvalido(f"CSV malformado: {erro}.") from None
    return linhas


_MARCAS_DTD = [m.encode(cod) for m in ("<!DOCTYPE", "<!ENTITY")
               for cod in ("ascii", "utf-16-le", "utf-16-be")]


def _tem_dtd(xml):
    maiusculo = xml.upper()
    return any(marca in maiusculo for marca in _MARCAS_DTD)


def _ler_xlsx(conteudo):
    import openpyxl
    import openpyxl.xml

    if not conteudo.startswith(b"PK\x03\x04"):
        raise ArquivoInvalido("O arquivo não é um .xlsx válido.")
    # Sem defusedxml, o openpyxl aceitaria entidades XML (XXE / "billion laughs")
    if not openpyxl.xml.DEFUSEDXML:
        raise ArquivoInvalido("Importação de .xlsx indisponível no servidor. Use .csv.")

    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as pacote:
            entradas = pacote.infolist()
            if len(entradas) > 200:
                raise ArquivoInvalido("O .xlsx tem estrutura inválida.")
            total = sum(e.file_size for e in entradas)
            if total > LIMITE_DESCOMPACTADO:
                raise ArquivoInvalido("O .xlsx descompactado é grande demais.")
            for e in entradas:
                if e.compress_size and e.file_size / e.compress_size > LIMITE_TAXA_COMPRESSAO \
                        and e.file_size > 1024 * 1024:
                    raise ArquivoInvalido("O .xlsx tem compressão suspeita e foi recusado.")
                if e.filename.lower().endswith("vbaproject.bin"):
                    raise ArquivoInvalido("O arquivo tem macros. Salve como .xlsx sem macros.")
            # Planilha legítima do Excel nunca tem DTD. Recusa aqui, antes do
            # openpyxl, para o resultado não depender do parser instalado (com
            # lxml as entidades são ignoradas em silêncio; com defusedxml, erro)
            for e in entradas:
                if e.filename.lower().endswith((".xml", ".rels", ".vml")):
                    if _tem_dtd(pacote.read(e)):
                        raise ArquivoInvalido("O .xlsx tem conteúdo não permitido (DTD/entidades XML).")
    except zipfile.BadZipFile:
        raise ArquivoInvalido("O arquivo não é um .xlsx válido.") from None

    try:
        livro = openpyxl.load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    except ArquivoInvalido:
        raise
    except Exception:  # defusedxml (DTD/entidades), XML quebrado, pacote incompleto
        raise ArquivoInvalido("O .xlsx está corrompido ou tem conteúdo não permitido.") from None

    try:
        planilha = livro["Clientes"] if "Clientes" in livro.sheetnames else livro.worksheets[0]
        linhas = []
        for indice, valores in enumerate(planilha.iter_rows(values_only=True, max_col=LIMITE_COLUNAS), start=1):
            if len(linhas) > LIMITE_LINHAS + 1:
                raise ArquivoInvalido(f"O arquivo passa de {LIMITE_LINHAS} linhas. Divida em arquivos menores.")
            linhas.append((indice, list(valores)))
        return linhas
    except ArquivoInvalido:
        raise
    except Exception:
        raise ArquivoInvalido("O .xlsx está corrompido ou tem conteúdo não permitido.") from None
    finally:
        livro.close()


# ---- Validação ---------------------------------------------------------------

def _vazia(valores):
    return all(v is None or (isinstance(v, str) and not v.strip()) for v in valores)


def _texto(valor):
    """Célula -> texto. Números inteiros sem ".0"; datas em AAAA-MM-DD."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "sim" if valor else "não"
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    if isinstance(valor, datetime):
        return valor.date().isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return unicodedata.normalize("NFC", str(valor)).strip()


def checar_texto(texto, rotulo, maximo, permitir_quebra=False, permitir_mais=False):
    """Retorna mensagem de erro ou None. Usado também pelo cadastro manual."""
    if not texto:
        return None
    controle = _CONTROLE if permitir_quebra else re.compile(r"[\x00-\x1f\x7f]")
    if controle.search(texto):
        return f"{rotulo} tem caracteres de controle não permitidos."
    if texto.startswith(INICIO_FORMULA) and not (permitir_mais and texto.startswith("+")):
        return f"{rotulo} não pode começar com = + - ou @ (parece uma fórmula de planilha)."
    if _HTML.search(texto):
        return f"{rotulo} não pode conter marcação HTML (<...>)."
    if len(texto) > maximo:
        return f"{rotulo} aceita até {maximo} caracteres."
    return None


def _valor_monetario(bruto):
    if isinstance(bruto, bool):
        raise ValueError
    if isinstance(bruto, (int, float)):
        return float(bruto)
    texto = _texto(bruto).replace("R$", "").replace(" ", "")
    if not texto:
        return None
    if "," in texto:  # formato brasileiro: 1.250,90
        texto = texto.replace(".", "").replace(",", ".")
    if not re.fullmatch(r"[0-9]+(\.[0-9]{1,2})?", texto):
        raise ValueError
    return float(texto)


def _dia(frequencia, bruto):
    if isinstance(bruto, (datetime, date)):  # "Data de vencimento" preenchida como data
        d = bruto.date() if isinstance(bruto, datetime) else bruto
        return ("dia_semana", d.isoweekday()) if frequencia == "semanal" else ("dia_mes", d.day)
    texto = _sem_acento(_texto(bruto)).lower().replace("feira", "").strip(" -")
    if frequencia == "semanal":
        if texto.isdigit() and 1 <= int(texto) <= 7:
            return "dia_semana", int(texto)
        if texto in DIAS_SEMANA_TEXTO:
            return "dia_semana", DIAS_SEMANA_TEXTO[texto]
        if texto.rstrip("a") in DIAS_SEMANA_TEXTO:
            return "dia_semana", DIAS_SEMANA_TEXTO[texto.rstrip("a")]
        raise ValueError
    texto = texto.removeprefix("dia").strip()
    if texto.isdigit() and 1 <= int(texto) <= 31:
        return "dia_mes", int(texto)
    raise ValueError


def mapear_cabecalho(linhas):
    """Acha a linha de cabeçalho (primeira não vazia) e o índice de cada coluna."""
    for posicao, (numero, valores) in enumerate(linhas):
        if _vazia(valores):
            continue
        indices, desconhecidas = {}, []
        for i, titulo in enumerate(valores):
            if titulo is None or not str(titulo).strip():
                continue
            chave = _CABECALHOS.get(_chave_cabecalho(titulo))
            if chave and chave not in indices:
                indices[chave] = i
            else:
                desconhecidas.append(str(titulo).strip()[:40])
        if "nome" not in indices:
            raise ArquivoInvalido(f"Cabeçalho não reconhecido na linha {numero}: falta a coluna "
                                  f"'{TITULOS['nome']}'. Use o modelo oficial.")
        return posicao, indices, desconhecidas
    raise ArquivoInvalido("A planilha não tem dados.")


def validar_linhas(linhas):
    """Retorna (registros, erros, avisos).

    registro = {"linha", "chave", "cliente": {...}, "recorrencia": {...} | None}
    erro     = {"linha", "coluna", "mensagem"}
    """
    posicao, indices, desconhecidas = mapear_cabecalho(linhas)
    avisos = [f"Coluna ignorada: {t}" for t in desconhecidas]
    registros, erros = [], []
    por_documento = {}

    dados = [(n, v) for n, v in linhas[posicao + 1:] if not _vazia(v)]
    if not dados:
        raise ArquivoInvalido("A planilha só tem o cabeçalho, sem clientes.")
    if len(dados) > LIMITE_LINHAS:
        raise ArquivoInvalido(f"O arquivo passa de {LIMITE_LINHAS} linhas. Divida em arquivos menores.")

    for numero, valores in dados:
        bruto = {chave: (valores[i] if i < len(valores) else None) for chave, i in indices.items()}
        erros_linha = []

        def erro(chave, mensagem):
            erros_linha.append({"linha": numero, "coluna": TITULOS[chave], "mensagem": mensagem})

        nome = _texto(bruto.get("nome"))
        if not nome:
            erro("nome", "Nome do cliente é obrigatório.")
        elif problema := checar_texto(nome, "Nome", 150):
            erro("nome", problema)

        documento, problema = normalizar_documento(
            bruto.get("documento") if isinstance(bruto.get("documento"), (int, float)) else _texto(bruto.get("documento")) or None)
        if problema:
            erro("documento", problema)

        email = _texto(bruto.get("email")) or None
        if email:
            if problema := checar_texto(email, "E-mail", 150):
                erro("email", problema)
            else:
                email = normalizar_email(email)
                if validar_email(email):
                    erro("email", "E-mail inválido.")

        telefone = _texto(bruto.get("telefone")) or None
        if telefone:
            if (problema := checar_texto(telefone, "Telefone", 30, permitir_mais=True)):
                erro("telefone", problema)
            elif not _TELEFONE.match(telefone):
                erro("telefone", "Telefone inválido. Use de 8 a 30 dígitos, com ( ) - + . ou espaços.")

        status_texto = _texto(bruto.get("status"))
        status = next((s for s in STATUS_VALIDOS if s.lower() == _sem_acento(status_texto).lower()), None) \
            if status_texto else "Lead"
        if status is None:
            erro("status", "Status inválido. Use Lead, Cliente ou Inativo.")

        recorrencia = None
        if any(_texto(bruto.get(c)) for c in CAMPOS_RECORRENCIA):
            recorrencia = _validar_recorrencia_linha(bruto, erro)

        cliente = {"nome": nome, "documento": documento, "email": email, "telefone": telefone, "status": status}

        # Mesmo CPF/CNPJ em várias linhas = mesmo cliente com várias recorrências
        chave = f"doc:{documento}" if documento else f"linha:{numero}"
        if documento and not erros_linha:
            anterior = por_documento.get(documento)
            if anterior and anterior["cliente"] != cliente:
                erro("documento", f"CPF/CNPJ repetido com dados diferentes da linha {anterior['linha']}. "
                                  "Repita os mesmos dados do cliente ou use outro CPF/CNPJ.")
            elif anterior and not recorrencia:
                erro("documento", f"CPF/CNPJ repetido da linha {anterior['linha']} sem recorrência nova.")

        if erros_linha:
            erros.extend(erros_linha)
            continue
        registro = {"linha": numero, "chave": chave, "cliente": cliente, "recorrencia": recorrencia}
        if documento:
            por_documento.setdefault(documento, registro)
        registros.append(registro)

    return registros, erros, avisos


def _validar_recorrencia_linha(bruto, erro):
    tipo = _sem_acento(_texto(bruto.get("rec_tipo"))).lower()
    frequencia = _sem_acento(_texto(bruto.get("rec_frequencia"))).lower()
    if tipo not in TIPOS:
        erro("rec_tipo", "Tipo de recorrência inválido. Use lembrete ou oportunidade.")
        return None
    if frequencia not in FREQUENCIAS:
        erro("rec_frequencia", "Frequência inválida. Use semanal ou mensal.")
        return None

    try:
        campo_dia, dia = _dia(frequencia, bruto.get("rec_dia"))
    except ValueError:
        erro("rec_dia", "Dia inválido. Semanal: segunda a domingo. Mensal: 1 a 31.")
        return None

    titulo = _texto(bruto.get("rec_titulo")) or "Compra recorrente"
    if problema := checar_texto(titulo, "Título", 150):
        erro("rec_titulo", problema)
        return None
    notas = _texto(bruto.get("rec_notas")) or None
    if notas and (problema := checar_texto(notas, "Notas", 2000, permitir_quebra=True)):
        erro("rec_notas", problema)
        return None

    try:
        valor = _valor_monetario(bruto.get("rec_valor")) if bruto.get("rec_valor") not in (None, "") else None
    except ValueError:
        erro("rec_valor", "Valor inválido. Use números, ex.: 1.250,90")
        return None

    campos, problema = validar_recorrencia({"tipo": tipo, "titulo": titulo, "valor": valor, "notas": notas,
                                            "frequencia": frequencia, campo_dia: dia})
    if problema:
        erro("rec_valor" if "valor" in problema else "rec_tipo", problema)
        return None
    return campos


def previa(registros):
    """As primeiras linhas como a pessoa vai ver depois de importar."""
    from recorrencia import descrever
    saida = []
    for r in registros[:LINHAS_PREVIA]:
        rec = r["recorrencia"]
        saida.append({
            "linha": r["linha"],
            **r["cliente"],
            "recorrencia": None if not rec else {
                "tipo": rec["tipo"], "titulo": rec["titulo"], "valor": rec["valor"],
                "descricao": descrever(rec["frequencia"], rec["dia_semana"], rec["dia_mes"]),
            },
        })
    return saida


# ---- Saída (modelo e exportação) --------------------------------------------

def neutralizar_celula(valor):
    """OWASP CSV Injection: texto que começa com = + - @ tab ou CR ganha um
    apóstrofo na frente e o Excel/LibreOffice o exibem como texto."""
    if isinstance(valor, str) and valor and valor[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + valor
    return valor


def gerar_csv(linhas):
    """CSV que o Excel em português abre direto: UTF-8 com BOM e ponto e vírgula."""
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    escritor.writerow([titulo for _, titulo, _ in COLUNAS])
    for linha in linhas:
        escritor.writerow([neutralizar_celula(v) if v is not None else "" for v in linha])
    return ("\ufeff" + saida.getvalue()).encode("utf-8")


def gerar_xlsx(linhas, com_instrucoes=True):
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    livro = openpyxl.Workbook()
    planilha = livro.active
    planilha.title = "Clientes"
    planilha.append([titulo for _, titulo, _ in COLUNAS])
    for celula in planilha[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor="0F969C")
        celula.alignment = Alignment(vertical="center", wrap_text=True)
    planilha.freeze_panes = "A2"
    for i, (chave, _, _) in enumerate(COLUNAS, start=1):
        letra = openpyxl.utils.get_column_letter(i)
        planilha.column_dimensions[letra].width = 34 if chave in ("nome", "rec_titulo", "rec_notas") else 20
        # CPF/CNPJ e telefone como TEXTO na coluna inteira: o Excel não come zeros
        # à esquerda (sem criar células vazias, que contariam como linhas)
        if chave in ("documento", "telefone"):
            planilha.column_dimensions[letra].number_format = "@"

    for linha in linhas:
        planilha.append([neutralizar_celula(v) for v in linha])

    # Listas suspensas nas colunas fechadas (ajudam, mas o servidor revalida tudo)
    def lista(chave, opcoes):
        coluna = openpyxl.utils.get_column_letter([c for c, _, _ in COLUNAS].index(chave) + 1)
        validacao = DataValidation(type="list", formula1=f'"{",".join(opcoes)}"', allow_blank=True)
        validacao.add(f"{coluna}2:{coluna}{LIMITE_LINHAS + 1}")
        planilha.add_data_validation(validacao)

    lista("status", STATUS_VALIDOS)
    lista("rec_tipo", TIPOS)
    lista("rec_frequencia", FREQUENCIAS)

    if com_instrucoes:
        ajuda = livro.create_sheet("Instruções")
        ajuda.append(["Coluna", "Como preencher"])
        for celula in ajuda[1]:
            celula.font = Font(bold=True)
        for _, titulo, texto in COLUNAS:
            ajuda.append([titulo, texto])
        ajuda.append([])
        ajuda.append(["Exemplo", "Padaria Estrela | 11.222.333/0001-81 | contato@padaria.com | (11) 3000-0003 | "
                                 "Cliente | oportunidade | semanal | segunda | Compra semanal de pães | 350,00"])
        ajuda.append(["Regras", "Máximo de 2000 linhas e 1 MB. Se alguma linha tiver erro, nada é importado "
                                "e a tela mostra a linha e a coluna para corrigir."])
        ajuda.column_dimensions["A"].width = 28
        ajuda.column_dimensions["B"].width = 110

    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()
