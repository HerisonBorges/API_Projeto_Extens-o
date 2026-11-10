import os

import psycopg2


def conectar_banco():
    # Credenciais vêm do ambiente; nenhuma senha fica no código.
    senha = os.getenv("DB_PASSWORD")

    if senha is None:
        raise RuntimeError("Variável de ambiente DB_PASSWORD não definida.")

    conexao = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "crm_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=senha
    )

    return conexao
