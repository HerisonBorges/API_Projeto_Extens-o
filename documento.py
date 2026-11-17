"""CPF e CNPJ (inclusive o CNPJ alfanumérico, emitido desde julho/2026).

normalizar_documento("123.456.789-09") -> ("12345678909", None)
normalizar_documento("12.ABC.345/01DE-35") -> ("12ABC34501DE35", None)

Dígito verificador: módulo 11. No CNPJ, cada caractere vale ASCII − 48
("0"-"9" = 0-9, "A" = 17 ... "Z" = 42), conforme a IN RFB nº 2.229/2024.
"""
import re

_SEPARADORES = re.compile(r"[\s./\-]")
_CPF = re.compile(r"^[0-9]{11}$")
_CNPJ = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")


def _dv_modulo_11(valores, pesos):
    resto = sum(v * p for v, p in zip(valores, pesos)) % 11
    return 0 if resto < 2 else 11 - resto


def cpf_valido(cpf):
    if not _CPF.match(cpf) or cpf == cpf[0] * 11:
        return False
    numeros = [int(c) for c in cpf]
    dv1 = _dv_modulo_11(numeros[:9], range(10, 1, -1))
    dv2 = _dv_modulo_11(numeros[:9] + [dv1], range(11, 1, -1))
    return numeros[9:] == [dv1, dv2]


def cnpj_valido(cnpj):
    if not _CNPJ.match(cnpj) or cnpj == cnpj[0] * 14:
        return False
    valores = [ord(c) - 48 for c in cnpj[:12]]
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    dv1 = _dv_modulo_11(valores, pesos1)
    dv2 = _dv_modulo_11(valores + [dv1], [6] + pesos1)
    return cnpj[12:] == f"{dv1}{dv2}"


def normalizar_documento(valor):
    """Retorna (documento_sem_pontuacao | None, erro | None). Vazio = sem documento.

    Número vindo do Excel perde zeros à esquerda (01234567890 vira 1234567890):
    completa com zeros até 11 (CPF) ou 14 (CNPJ) antes de validar.
    """
    if valor is None:
        return None, None
    if isinstance(valor, bool):
        return None, "CPF/CNPJ inválido."
    if isinstance(valor, float):
        if not valor.is_integer():
            return None, "CPF/CNPJ inválido."
        valor = int(valor)
    if isinstance(valor, int):
        texto = str(valor)
        texto = texto.zfill(11) if len(texto) <= 11 else texto.zfill(14)
    elif isinstance(valor, str):
        texto = _SEPARADORES.sub("", valor).upper()
    else:
        return None, "CPF/CNPJ inválido."

    if not texto:
        return None, None
    if len(texto) == 11 and cpf_valido(texto):
        return texto, None
    if len(texto) == 14 and cnpj_valido(texto):
        return texto, None
    if len(texto) in (11, 14):
        return None, "CPF/CNPJ com dígito verificador inválido."
    return None, "CPF/CNPJ deve ter 11 (CPF) ou 14 (CNPJ) caracteres."


def formatar_documento(documento):
    if not documento:
        return None
    if len(documento) == 11:
        return f"{documento[:3]}.{documento[3:6]}.{documento[6:9]}-{documento[9:]}"
    return f"{documento[:2]}.{documento[2:5]}.{documento[5:8]}/{documento[8:12]}-{documento[12:]}"
