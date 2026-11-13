"""Pool de conexões com o PostgreSQL (Supabase).

Abrir uma conexão SSL com o Supabase custa centenas de ms. O pool mantém
conexões abertas e as reaproveita entre requisições.

Duas formas de uso:

    # Recomendado para código novo: devolução garantida
    with get_db_connection() as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(...)
        conexao.commit()

    # Compatível com as rotas existentes
    conexao = conectar_banco()
    ...
    conexao.close()   # devolve ao pool (não fecha o socket)

Dentro de uma requisição Flask, conexões não devolvidas (ex.: exceção antes
do close) são recuperadas em devolver_conexoes_da_requisicao, registrada
como teardown no app.py.
"""
import atexit
import os
import threading
import time
from contextlib import contextmanager

import psycopg2
from psycopg2 import extensions, pool

try:
    from flask import g, has_app_context
except ImportError:  # scripts sem Flask
    g = None

    def has_app_context():
        return False


POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))

# Quanto tempo uma requisição espera por uma conexão livre antes de falhar
POOL_ESPERA_SEGUNDOS = float(os.getenv("DB_POOL_TIMEOUT", "10"))

# Conexões ociosas há mais que isso são testadas (SELECT 1) antes do uso
PING_APOS_OCIOSA_SEGUNDOS = 60

_pool = None
_trava_criacao = threading.Lock()
_vagas = threading.BoundedSemaphore(POOL_MAX)


class PoolEsgotado(RuntimeError):
    pass


def _criar_pool():
    senha = os.getenv("DB_PASSWORD")

    if senha is None:
        raise RuntimeError("Variável de ambiente DB_PASSWORD não definida.")

    # sslmode vem de PGSSLMODE, lido diretamente pela libpq
    return pool.ThreadedConnectionPool(
        POOL_MIN,
        POOL_MAX,
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "crm_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=senha,
        # Sem isso, um banco inacessível trava o worker do Gunicorn indefinidamente
        connect_timeout=int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
        application_name=os.getenv("DB_APPLICATION_NAME", "sandro-crm-api"),
    )


def _obter_pool():
    global _pool

    if _pool is None or _pool.closed:
        with _trava_criacao:
            if _pool is None or _pool.closed:
                _pool = _criar_pool()

    return _pool


def _conexao_saudavel(conexao, ultimo_uso):
    if conexao.closed:
        return False

    if time.monotonic() - ultimo_uso < PING_APOS_OCIOSA_SEGUNDOS:
        return True

    try:
        with conexao.cursor() as cursor:
            cursor.execute("SELECT 1;")
        conexao.rollback()
        return True
    except psycopg2.Error:
        return False


class ConexaoDoPool:
    """Envolve uma conexão do pool. close() devolve em vez de fechar."""

    _ultimo_uso = {}

    def __init__(self, pool_atual, conexao):
        self._pool_atual = pool_atual
        self._conexao = conexao
        self._devolvida = False

    def __getattr__(self, nome):
        if self._devolvida:
            raise psycopg2.InterfaceError("Conexão já devolvida ao pool.")
        return getattr(self._conexao, nome)

    @property
    def devolvida(self):
        return self._devolvida

    def close(self):
        if self._devolvida:
            return

        self._devolvida = True
        conexao = self._conexao
        descartar = bool(conexao.closed)

        if not descartar:
            try:
                # Nada de transação aberta ou abortada voltando para o pool
                if conexao.get_transaction_status() != extensions.TRANSACTION_STATUS_IDLE:
                    conexao.rollback()
            except psycopg2.Error:
                descartar = True

        if descartar:
            ConexaoDoPool._ultimo_uso.pop(id(conexao), None)
        else:
            ConexaoDoPool._ultimo_uso[id(conexao)] = time.monotonic()

        try:
            self._pool_atual.putconn(conexao, close=descartar)
        except pool.PoolError:
            pass  # pool já foi fechado (encerramento do processo)
        finally:
            _vagas.release()


def conectar_banco():
    """Retorna uma conexão do pool. Chame close() para devolvê-la."""
    if not _vagas.acquire(timeout=POOL_ESPERA_SEGUNDOS):
        raise PoolEsgotado(
            f"Nenhuma conexão livre em {POOL_ESPERA_SEGUNDOS:.0f}s "
            f"(DB_POOL_MAX={POOL_MAX})."
        )

    try:
        pool_atual = _obter_pool()

        # Descarta conexões que o servidor derrubou enquanto estavam ociosas.
        # Conexão sem registro de uso (ex.: criada no início do pool) é testada.
        for _ in range(POOL_MAX + 1):
            conexao = pool_atual.getconn()
            ultimo_uso = ConexaoDoPool._ultimo_uso.get(id(conexao), 0.0)

            if _conexao_saudavel(conexao, ultimo_uso):
                break

            ConexaoDoPool._ultimo_uso.pop(id(conexao), None)
            pool_atual.putconn(conexao, close=True)
        else:
            raise psycopg2.OperationalError("Não foi possível obter conexão saudável.")
    except BaseException:
        _vagas.release()
        raise

    envelope = ConexaoDoPool(pool_atual, conexao)

    if has_app_context():
        g.setdefault("_conexoes_do_pool", []).append(envelope)

    return envelope


@contextmanager
def get_db_connection():
    """Context manager: a conexão sempre volta ao pool, mesmo com exceção."""
    conexao = conectar_banco()
    try:
        yield conexao
    finally:
        conexao.close()


def devolver_conexoes_da_requisicao(_excecao=None):
    """Teardown do Flask: recupera conexões que a rota não devolveu."""
    for conexao in g.pop("_conexoes_do_pool", []):
        if not conexao.devolvida:
            conexao.close()


def conexoes_em_uso():
    """Quantas conexões estão emprestadas agora (diagnóstico e testes)."""
    return 0 if _pool is None or _pool.closed else len(_pool._used)


def fechar_pool():
    global _pool

    if _pool is not None and not _pool.closed:
        _pool.closeall()

    _pool = None


atexit.register(fechar_pool)
