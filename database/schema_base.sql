-- SANDRO CRM - tabelas base (rodar ANTES de migracao_oportunidades_tarefas.sql)
-- Estrutura deduzida das queries em routes/auth.py, clientes.py e configuracoes.py.
-- Idempotente: não altera tabelas que já existem.

CREATE TABLE IF NOT EXISTS empresas (
    id        SERIAL PRIMARY KEY,
    nome      VARCHAR(150) NOT NULL,
    email     VARCHAR(150),
    criado_em TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS usuarios (
    id         SERIAL PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    nome       VARCHAR(150) NOT NULL,
    email      VARCHAR(150) NOT NULL UNIQUE,
    senha      VARCHAR(255) NOT NULL,          -- hash bcrypt
    criado_em  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS clientes (
    id         SERIAL PRIMARY KEY,
    empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    nome       VARCHAR(150) NOT NULL,
    email      VARCHAR(150),
    telefone   VARCHAR(30),
    status     VARCHAR(30) NOT NULL DEFAULT 'Lead',
    criado_em  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clientes_empresa ON clientes (empresa_id);

CREATE TABLE IF NOT EXISTS configuracoes (
    id                 SERIAL PRIMARY KEY,
    empresa_id         INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    notificacoes_email BOOLEAN NOT NULL DEFAULT TRUE,
    tema_escuro        BOOLEAN NOT NULL DEFAULT TRUE
);
