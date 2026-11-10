"""Comportamento do pool de conexões (database/conexao.py), contra o banco do .env.

Uso:
    python3 -m unittest tests.test_pool -v
"""
import threading
import time
import unittest
import uuid

import app as aplicacao
from database import conexao as modulo
from database.conexao import (
    PoolEsgotado,
    conectar_banco,
    conexoes_em_uso,
    get_db_connection,
)


def pid(conexao):
    with conexao.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid();")
        return cursor.fetchone()[0]


class PoolDeConexoes(unittest.TestCase):

    def test_01_reaproveita_a_mesma_conexao(self):
        """Dado uma conexão devolvida / Quando peço outra / Então recebo a mesma sessão."""
        with get_db_connection() as c1:
            primeiro = pid(c1)
        with get_db_connection() as c2:
            segundo = pid(c2)
        self.assertEqual(primeiro, segundo)

    def test_02_devolucao_desfaz_transacao_pendente(self):
        """Dado um INSERT sem commit / Quando a conexão volta ao pool /
        Então o INSERT é desfeito e a conexão volta limpa."""
        nome = f"Empresa rollback {uuid.uuid4().hex[:8]}"
        c = conectar_banco()
        with c.cursor() as cursor:
            cursor.execute("INSERT INTO empresas (nome) VALUES (%s);", (nome,))
        c.close()

        with get_db_connection() as c2:
            with c2.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM empresas WHERE nome = %s;", (nome,))
                self.assertEqual(cursor.fetchone()[0], 0)

    def test_03_conexao_esquecida_e_recuperada_no_fim_da_requisicao(self):
        """Dado uma rota que pega conexão e lança exceção antes do close /
        Então o teardown do Flask devolve a conexão ao pool."""
        antes = conexoes_em_uso()

        with self.assertRaises(ZeroDivisionError):
            with aplicacao.app.test_request_context("/"):
                conectar_banco()
                self.assertEqual(conexoes_em_uso(), antes + 1)
                1 / 0

        self.assertEqual(conexoes_em_uso(), antes)

    def test_04_usar_conexao_devolvida_falha(self):
        """Dado uma conexão já devolvida / Quando tento usá-la / Então recebo erro."""
        c = conectar_banco()
        c.close()
        with self.assertRaises(Exception):
            c.cursor()
        c.close()  # fechar duas vezes não quebra nem libera vaga a mais

    def test_05_conexao_morta_e_descartada(self):
        """Dado uma conexão cujo socket caiu / Quando é devolvida /
        Então é descartada e a próxima conexão funciona."""
        c = conectar_banco()
        c._conexao.close()
        c.close()
        with get_db_connection() as c2:
            self.assertIsInstance(pid(c2), int)

    def test_06_mais_requisicoes_que_conexoes_esperam_na_fila(self):
        """Dado 15 threads e DB_POOL_MAX=10 / Então todas concluem e nunca há mais
        de 10 conexões emprestadas."""
        erros, pico = [], [0]
        trava = threading.Lock()

        def trabalho():
            try:
                with get_db_connection() as c:
                    with trava:
                        pico[0] = max(pico[0], conexoes_em_uso())
                    pid(c)
                    time.sleep(0.3)
            except Exception as e:  # noqa: BLE001
                erros.append(e)

        threads = [threading.Thread(target=trabalho) for _ in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(erros, [])
        self.assertLessEqual(pico[0], modulo.POOL_MAX)

    def test_07_pool_esgotado_falha_com_mensagem_clara(self):
        """Dado todas as vagas ocupadas / Quando passa o tempo de espera /
        Então recebo PoolEsgotado em vez de travar para sempre."""
        espera_original = modulo.POOL_ESPERA_SEGUNDOS
        modulo.POOL_ESPERA_SEGUNDOS = 0.5
        ocupadas = []
        try:
            for _ in range(modulo.POOL_MAX):
                ocupadas.append(conectar_banco())
            with self.assertRaises(PoolEsgotado):
                conectar_banco()
        finally:
            modulo.POOL_ESPERA_SEGUNDOS = espera_original
            for c in ocupadas:
                c.close()

        with get_db_connection() as c:
            self.assertIsInstance(pid(c), int)


if __name__ == "__main__":
    unittest.main(verbosity=2)
