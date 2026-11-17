"""Regras de recorrência: validação e cálculo de datas.

Usado pela API (routes/recorrencias.py), pela importação de planilhas e pelo
worker (database/worker_recorrencias.py). Sem acesso a banco: funções puras,
fáceis de testar.

Calendário: as datas são do calendário da EMPRESA (TZ_EMPRESA), nunca UTC.
"""
import calendar
from datetime import date, timedelta

TIPOS = ("lembrete", "oportunidade")
FREQUENCIAS = ("semanal", "mensal")
TITULO_MAXIMO = 150
NOTAS_MAXIMO = 2000
VALOR_MAXIMO = 9_999_999_999.99  # NUMERIC(12,2)

# ISO 8601: 1 = segunda ... 7 = domingo (date.isoweekday)
DIAS_SEMANA = {1: "segunda-feira", 2: "terça-feira", 3: "quarta-feira", 4: "quinta-feira",
               5: "sexta-feira", 6: "sábado", 7: "domingo"}


def dia_no_mes(ano, mes, dia):
    """"Todo dia 31" em fevereiro vira o último dia do mês (28 ou 29)."""
    return date(ano, mes, min(dia, calendar.monthrange(ano, mes)[1]))


def proxima_ocorrencia(frequencia, dia_semana, dia_mes, a_partir_de, incluir_o_dia=True):
    """Primeira data da regra a partir de `a_partir_de`.

    incluir_o_dia=True: se `a_partir_de` já é um dia da regra, ele mesmo conta
    (regra criada numa segunda, "toda segunda" vence hoje).
    """
    inicio = a_partir_de if incluir_o_dia else a_partir_de + timedelta(days=1)

    if frequencia == "semanal":
        return inicio + timedelta(days=(dia_semana - inicio.isoweekday()) % 7)

    candidata = dia_no_mes(inicio.year, inicio.month, dia_mes)
    if candidata >= inicio:
        return candidata
    ano, mes = (inicio.year + 1, 1) if inicio.month == 12 else (inicio.year, inicio.month + 1)
    return dia_no_mes(ano, mes, dia_mes)


def ocorrencias_vencidas(regra, hoje, limite=12):
    """Datas da regra de `proxima_execucao` até `hoje` (inclusive), em ordem.

    Se o worker ficou parado, cada data perdida gera seu evento, até `limite`
    (as mais recentes). Retorna (datas, proxima_depois, puladas).
    """
    datas = []
    atual = regra["proxima_execucao"]
    while atual <= hoje:
        datas.append(atual)
        atual = proxima_ocorrencia(regra["frequencia"], regra["dia_semana"], regra["dia_mes"],
                                   atual, incluir_o_dia=False)
    puladas = max(0, len(datas) - limite)
    return datas[puladas:], atual, puladas


def descrever(frequencia, dia_semana, dia_mes):
    if frequencia == "semanal":
        dia = DIAS_SEMANA[dia_semana]
        return f"Todo {dia}" if dia_semana in (6, 7) else f"Toda {dia}"
    return f"Todo dia {dia_mes}" + (" (ou o último dia do mês)" if dia_mes > 28 else "")


def _inteiro(valor):
    if isinstance(valor, bool):
        raise ValueError
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    if isinstance(valor, str) and valor.strip().isdigit():
        return int(valor.strip())
    raise ValueError


def validar_recorrencia(dados):
    """Valida o corpo de criação/edição. Retorna (campos, erro).

    Campos: tipo, titulo, valor, notas, frequencia, dia_semana, dia_mes.
    """
    tipo = dados.get("tipo")
    if tipo not in TIPOS:
        return None, "tipo inválido. Use 'lembrete' ou 'oportunidade'."

    titulo = dados.get("titulo")
    if not isinstance(titulo, str) or not titulo.strip():
        return None, "titulo é obrigatório."
    titulo = titulo.strip()
    if len(titulo) > TITULO_MAXIMO:
        return None, f"titulo aceita até {TITULO_MAXIMO} caracteres."

    valor = dados.get("valor")
    if valor in (None, ""):
        valor = None
    elif isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None, "valor deve ser um número."
    elif not 0 <= valor <= VALOR_MAXIMO:
        return None, "valor deve estar entre 0 e 9.999.999.999,99."
    else:
        valor = round(float(valor), 2)
    if tipo == "lembrete":
        valor = None  # lembrete não tem valor

    notas = dados.get("notas")
    if notas is not None:
        if not isinstance(notas, str):
            return None, "notas inválidas."
        notas = notas.strip() or None
        if notas and len(notas) > NOTAS_MAXIMO:
            return None, f"notas aceitam até {NOTAS_MAXIMO} caracteres."

    frequencia = dados.get("frequencia")
    if frequencia not in FREQUENCIAS:
        return None, "frequencia inválida. Use 'semanal' ou 'mensal'."

    dia_semana = dia_mes = None
    try:
        if frequencia == "semanal":
            dia_semana = _inteiro(dados.get("dia_semana"))
            if not 1 <= dia_semana <= 7:
                raise ValueError
        else:
            dia_mes = _inteiro(dados.get("dia_mes"))
            if not 1 <= dia_mes <= 31:
                raise ValueError
    except (TypeError, ValueError):
        if frequencia == "semanal":
            return None, "dia_semana inválido. Use de 1 (segunda) a 7 (domingo)."
        return None, "dia_mes inválido. Use de 1 a 31."

    return {
        "tipo": tipo,
        "titulo": titulo,
        "valor": valor,
        "notas": notas,
        "frequencia": frequencia,
        "dia_semana": dia_semana,
        "dia_mes": dia_mes,
    }, None


def hoje_na_empresa(cursor, fuso):
    """Data de hoje no calendário da empresa, pelo relógio do banco."""
    cursor.execute("SELECT (NOW() AT TIME ZONE %s)::date;", (fuso,))
    return cursor.fetchone()[0]
