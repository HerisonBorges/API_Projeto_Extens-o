import psycopg2


def conectar_banco():
    conexao = psycopg2.connect(
        host="localhost",
        database="crm_db",
        user="postgres",
        password="123456"
    )

    return conexao