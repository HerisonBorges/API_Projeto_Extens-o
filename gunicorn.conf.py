"""Gunicorn em produção: `gunicorn app:app` (este arquivo é lido automaticamente).

Conexões com o banco: cada worker tem o próprio pool (DB_POOL_MAX).
Total no Supabase = WEB_CONCURRENCY x DB_POOL_MAX (padrões: 2 x 5 = 10).
Some com o worker de reciclagem antes de aumentar.
"""
import os

# O PaaS informa a porta em $PORT
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# Threads: a maior parte do tempo de cada requisição é espera pelo banco (I/O)
worker_class = "gthread"
workers = int(os.getenv("WEB_CONCURRENCY", "2"))
threads = int(os.getenv("GUNICORN_THREADS", "4"))

# Pool criado depois do fork, um por worker (nunca compartilhar sockets entre processos)
preload_app = False

timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))
graceful_timeout = 30
keepalive = 5

# Recicla workers aos poucos para conter vazamento de memória
max_requests = 1000
max_requests_jitter = 100

# Logs no stdout/stderr: o painel do PaaS coleta
accesslog = "-"
errorlog = "-"
loglevel = os.getenv("LOG_LEVEL", "info").lower()

# O proxy do PaaS fica na frente; o ProxyFix do app.py interpreta X-Forwarded-*
forwarded_allow_ips = "*"
