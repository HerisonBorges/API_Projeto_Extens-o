"""Configuração por ambiente e validação de inicialização.

APP_ENV=producao   -> exige CORS_ORIGINS explícito (https), sem Swagger por padrão
APP_ENV=desenvolvimento (padrão) -> libera o front local (portas 3000 e 5173)

Em qualquer ambiente a API se recusa a subir sem SECRET_KEY forte e sem
DB_PASSWORD: é melhor falhar no deploy do que rodar com uma chave pública.
"""
import os
import re

CHAVES_INSEGURAS = {"troque-esta-chave-em-producao", "<chave-longa-e-aleatoria>"}
TAMANHO_MINIMO_CHAVE = 32

ORIGENS_DESENVOLVIMENTO = ["http://localhost:3000", "http://localhost:5173"]

_ORIGEM = re.compile(r"^https?://[^/\s:]+(:\d{1,5})?$")
_LOCAL = re.compile(r"^http://(localhost|127\.0\.0\.1)(:\d{1,5})?$")


def ambiente(env=None):
    env = os.environ if env is None else env
    return (env.get("APP_ENV") or "desenvolvimento").strip().lower()


def em_producao(env=None):
    return ambiente(env) == "producao"


def ler_origens_cors(valor, producao):
    """'https://a.app, https://b.app/' -> ['https://a.app', 'https://b.app'].

    Lança ValueError para '*', URL malformada ou http fora de localhost em produção.
    """
    origens = [o.strip().rstrip("/") for o in (valor or "").split(",") if o.strip()]

    for origem in origens:
        if origem == "*":
            raise ValueError("CORS_ORIGINS não pode ser '*': liste as origens do front.")
        if not _ORIGEM.match(origem):
            raise ValueError(f"Origem CORS inválida: {origem!r} (use esquema://host[:porta]).")
        if producao and origem.startswith("http://") and not _LOCAL.match(origem):
            raise ValueError(f"Em produção use https: {origem!r}.")

    return origens


def origens_cors(env=None):
    env = os.environ if env is None else env
    producao = em_producao(env)
    origens = ler_origens_cors(env.get("CORS_ORIGINS"), producao)
    return origens or ([] if producao else ORIGENS_DESENVOLVIMENTO)


def problemas_de_configuracao(env=None):
    """Lista o que impede a API de subir com segurança (vazia = tudo certo)."""
    env = os.environ if env is None else env
    problemas = []

    chave = env.get("SECRET_KEY") or ""
    if not chave:
        problemas.append("SECRET_KEY não definida.")
    elif chave in CHAVES_INSEGURAS:
        problemas.append("SECRET_KEY usa um valor de exemplo público.")
    elif len(chave) < TAMANHO_MINIMO_CHAVE:
        problemas.append(f"SECRET_KEY precisa de pelo menos {TAMANHO_MINIMO_CHAVE} caracteres.")

    if not env.get("DB_PASSWORD"):
        problemas.append("DB_PASSWORD não definida.")

    try:
        origens = origens_cors(env)
        if em_producao(env) and not origens:
            problemas.append("CORS_ORIGINS é obrigatório em produção (ex.: https://sandro-crm.netlify.app).")
    except ValueError as erro:
        problemas.append(str(erro))

    if ambiente(env) not in ("producao", "desenvolvimento"):
        problemas.append(f"APP_ENV inválido: {ambiente(env)!r} (use producao ou desenvolvimento).")

    return problemas


def validar_configuracao(env=None):
    problemas = problemas_de_configuracao(env)
    if problemas:
        raise RuntimeError(
            "Configuração inválida, a API não vai subir:\n- " + "\n- ".join(problemas)
        )
