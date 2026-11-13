"""Aplica os scripts de ARQUIVOS, em ordem, no banco do .env.

Uso (na raiz do projeto):
    python3 -m database.aplicar_migracoes

Cada arquivo roda em uma transação: se falhar, nada daquele arquivo é aplicado.
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from database.conexao import conectar_banco  # noqa: E402


PASTA = Path(__file__).resolve().parent
ARQUIVOS = [
    "schema_base.sql",
    "migracao_oportunidades_tarefas.sql",
    "migracao_reciclagem_horarios.sql",
    "migracao_interacoes_responsavel.sql",
    "migracao_iam_usuarios.sql",
    "migracao_clientes_edicao.sql",
    "migracao_fuso_horario.sql",
]


def main():
    conexao = conectar_banco()

    try:
        for nome in ARQUIVOS:
            sql = (PASTA / nome).read_text(encoding="utf-8")

            try:
                with conexao.cursor() as cursor:
                    cursor.execute(sql)
                conexao.commit()
                print(f"OK    {nome}")
            except Exception as erro:
                conexao.rollback()
                print(f"FALHA {nome}: {erro}")
                return 1
    finally:
        conexao.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
