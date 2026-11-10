-- SANDRO CRM - migração idempotente (pode rodar mais de uma vez)
-- Banco: crm_db

-- RBAC (RNF04): perfil do usuário
ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS perfil VARCHAR(20) NOT NULL DEFAULT 'Gestor'
    CHECK (perfil IN ('Gestor', 'Atendimento'));

-- Oportunidades (funil)
CREATE TABLE IF NOT EXISTS oportunidades (
    id                  SERIAL PRIMARY KEY,
    empresa_id          INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    cliente_id          INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
    titulo              VARCHAR(150) NOT NULL,
    valor               NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (valor >= 0),
    etapa               VARCHAR(30) NOT NULL DEFAULT 'Prospecção'
                        CHECK (etapa IN ('Prospecção','Qualificação','Proposta','Negociação','Fechado')),
    criado_em           TIMESTAMP NOT NULL DEFAULT NOW(),
    etapa_atualizada_em TIMESTAMP NOT NULL DEFAULT NOW()
);

ALTER TABLE oportunidades ADD COLUMN IF NOT EXISTS criado_em TIMESTAMP NOT NULL DEFAULT NOW();
ALTER TABLE oportunidades ADD COLUMN IF NOT EXISTS etapa_atualizada_em TIMESTAMP NOT NULL DEFAULT NOW();

CREATE INDEX IF NOT EXISTS idx_oportunidades_empresa_etapa ON oportunidades (empresa_id, etapa);
CREATE INDEX IF NOT EXISTS idx_oportunidades_cliente ON oportunidades (cliente_id);

-- Tarefas / follow-up
CREATE TABLE IF NOT EXISTS tarefas (
    id              SERIAL PRIMARY KEY,
    empresa_id      INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    cliente_id      INTEGER REFERENCES clientes(id) ON DELETE SET NULL,
    titulo          VARCHAR(150) NOT NULL,
    descricao       TEXT,
    data_vencimento DATE,
    concluida       BOOLEAN NOT NULL DEFAULT FALSE
);

ALTER TABLE tarefas
    ADD COLUMN IF NOT EXISTS oportunidade_id INTEGER REFERENCES oportunidades(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_tarefas_empresa_venc ON tarefas (empresa_id, concluida, data_vencimento);
CREATE INDEX IF NOT EXISTS idx_tarefas_oportunidade ON tarefas (oportunidade_id);

-- LGPD (RNF05): excluir/anonimizar cliente não apaga histórico financeiro.
-- SET NULL exige que a coluna aceite NULL.
ALTER TABLE oportunidades ALTER COLUMN cliente_id DROP NOT NULL;
ALTER TABLE oportunidades
    DROP CONSTRAINT IF EXISTS oportunidades_cliente_id_fkey,
    ADD CONSTRAINT oportunidades_cliente_id_fkey
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE SET NULL;

ALTER TABLE tarefas ALTER COLUMN cliente_id DROP NOT NULL;
ALTER TABLE tarefas
    DROP CONSTRAINT IF EXISTS tarefas_cliente_id_fkey,
    ADD CONSTRAINT tarefas_cliente_id_fkey
    FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE SET NULL;

-- RF04: dias CORRIDOS para alerta de orçamento parado. Default oficial = 7.
ALTER TABLE configuracoes
    ADD COLUMN IF NOT EXISTS dias_alerta_orcamento INTEGER NOT NULL DEFAULT 7
    CHECK (dias_alerta_orcamento > 0);

-- Uma linha de configuração por empresa (necessário para o upsert do PUT /configuracoes).
-- Falha se já houver empresa_id duplicado: nesse caso, remova as duplicatas antes.
CREATE UNIQUE INDEX IF NOT EXISTS uq_configuracoes_empresa ON configuracoes (empresa_id);

-- SUPABASE: tabelas do schema public ficam expostas pela API REST (PostgREST)
-- para quem tiver a anon key. Ligar RLS sem políticas bloqueia esse acesso.
-- A API Flask conecta como dono das tabelas, que ignora RLS, então nada muda para ela.
ALTER TABLE empresas      ENABLE ROW LEVEL SECURITY;
ALTER TABLE usuarios      ENABLE ROW LEVEL SECURITY;
ALTER TABLE clientes      ENABLE ROW LEVEL SECURITY;
ALTER TABLE configuracoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE oportunidades ENABLE ROW LEVEL SECURITY;
ALTER TABLE tarefas       ENABLE ROW LEVEL SECURITY;
