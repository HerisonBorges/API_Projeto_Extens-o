"""Regras de IAM do SANDRO CRM (identidade, senhas e auditoria).

Política de senha (alinhada ao NIST SP 800-63B: comprimento e lista de
bloqueio, em vez de regras de composição que levam a senhas previsíveis):
  - mínimo de 10 caracteres
  - máximo de 72 bytes (limite do bcrypt; acima disso ele rejeita)
  - fora da lista de senhas comuns
  - diferente do e-mail e da parte antes do @

Senha temporária (criação, redefinição, reativação): gerada pelo sistema,
mostrada uma única vez, vale SENHA_TEMPORARIA_HORAS e obriga a troca.
"""
import json
import re
import secrets

import bcrypt
from flask import request

SENHA_MINIMO = 10
SENHA_MAXIMO_BYTES = 72
SENHA_TEMPORARIA_HORAS = 72

TENTATIVAS_ANTES_DO_BLOQUEIO = 5
MINUTOS_DE_BLOQUEIO = 15

PERFIS = ("Gestor", "Atendimento")

SENHAS_COMUNS = {
    "1234567890", "12345678910", "0123456789", "1111111111", "0000000000",
    "qwertyuiop", "asdfghjkl", "senha12345", "senha123456", "senhasenha",
    "password123", "password1234", "passw0rd123", "abc1234567", "abcdefghij",
    "mudar12345", "mudar123456", "trocar12345", "admin12345", "admin123456",
    "iloveyou12", "brasil1234", "brasil12345", "gestor1234", "gestor12345",
    "sandro1234", "sandrocrm1", "sandrocrm123", "crm1234567", "teste12345",
    "teste123456", "123456789a", "a123456789", "qwerty1234", "q1w2e3r4t5",
}

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Alfabeto sem caracteres ambíguos (0/O, 1/l/I) para ditar por telefone
_ALFABETO = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# Hash fixo para comparar quando o e-mail não existe: o login leva o mesmo
# tempo com ou sem conta, e não dá para descobrir e-mails pelo tempo de resposta
HASH_FICTICIO = bcrypt.hashpw(b"conta-inexistente", bcrypt.gensalt()).decode()


def normalizar_email(email):
    return email.strip().lower() if isinstance(email, str) else None


def validar_email(email):
    if not email or len(email) > 150 or not _EMAIL.match(email):
        return "E-mail inválido."
    return None


def validar_nome(nome):
    if not isinstance(nome, str) or not nome.strip():
        return "Nome é obrigatório."
    if len(nome.strip()) > 150:
        return "Nome aceita até 150 caracteres."
    return None


def validar_senha(senha, email=None):
    """Retorna a mensagem do problema ou None se a senha atende à política."""
    if not isinstance(senha, str):
        return "Senha é obrigatória."
    if len(senha) < SENHA_MINIMO:
        return f"A senha precisa de pelo menos {SENHA_MINIMO} caracteres."
    if len(senha.encode("utf-8")) > SENHA_MAXIMO_BYTES:
        return f"A senha aceita até {SENHA_MAXIMO_BYTES} bytes (cerca de 72 caracteres sem acento)."
    if senha.lower() in SENHAS_COMUNS or len(set(senha)) < 4:
        return "Esta senha é muito comum. Escolha outra."
    if email:
        email = email.lower()
        if senha.lower() in (email, email.split("@")[0]):
            return "A senha não pode ser igual ao seu e-mail."
    return None


def gerar_hash(senha):
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def senha_confere(senha, hash_salvo):
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), (hash_salvo or HASH_FICTICIO).encode("utf-8"))
    except ValueError:
        # Senha acima de 72 bytes ou hash corrompido: nunca autentica
        return False


def gerar_senha_temporaria(tamanho=14):
    """Senha aleatória criptograficamente segura, com letras e números."""
    while True:
        senha = "".join(secrets.choice(_ALFABETO) for _ in range(tamanho))
        if (any(c.islower() for c in senha) and any(c.isupper() for c in senha)
                and any(c.isdigit() for c in senha)):
            return senha


def ip_da_requisicao():
    # Atrás do PaaS, o ProxyFix do app.py já coloca o IP real em remote_addr
    return (request.remote_addr or "")[:64] if request else None


def auditar(cursor, empresa_id, acao, ator_id=None, alvo_id=None, detalhes=None):
    """Registra o evento na MESMA transação da mudança: ou os dois, ou nenhum.

    Nunca passe senhas, hashes ou tokens em `detalhes`.
    """
    cursor.execute("""
        INSERT INTO auditoria_usuarios (empresa_id, ator_id, alvo_id, acao, detalhes, ip)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s);
    """, (empresa_id, ator_id, alvo_id, acao,
          json.dumps(detalhes or {}, ensure_ascii=False), ip_da_requisicao()))
