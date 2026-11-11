-- SANDRO CRM - Interações com cliente (RF02) e responsável pela oportunidade
-- Idempotente. Requer as migrações anteriores.

CREATE TABLE IF NOT EXISTS interacoes (
    id              SERIAL PRIMARY KEY,
    empresa_id      INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    -- Histórico é dado pessoal do cliente: some junto com ele (LGPD)
    cliente_id      INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    oportunidade_id INTEGER NULL REFERENCES oportunidades(id) ON DELETE SET NULL,
    usuario_id      INTEGER NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    tipo            VARCHAR(20) NOT NULL
                    CHECK (tipo IN ('Ligação', 'WhatsApp', 'E-mail', 'Reunião')),
    descricao       TEXT NOT NULL CHECK (length(btrim(descricao)) > 0),
    criado_em       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_interacoes_empresa_data ON interacoes (empresa_id, criado_em DESC);
CREATE INDEX IF NOT EXISTS idx_interacoes_cliente_data ON interacoes (cliente_id, criado_em DESC);

-- Mesmo bloqueio da API REST do Supabase aplicado às outras tabelas
ALTER TABLE interacoes ENABLE ROW LEVEL SECURITY;

-- Responsável pela oportunidade (exibido nos cards do Kanban)
ALTER TABLE oportunidades
    ADD COLUMN IF NOT EXISTS responsavel_id INTEGER NULL
    REFERENCES usuarios(id) ON DELETE SET NULL;
