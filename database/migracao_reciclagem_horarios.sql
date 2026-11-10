-- SANDRO CRM - Janela de acesso por horário (RBAC estendido) e reciclagem pós-venda
-- Idempotente: pode rodar mais de uma vez. Requer migracao_oportunidades_tarefas.sql.

-- ---------------------------------------------------------------------------
-- REQUISITO 1: janela de acesso por usuário
-- NULL nos dois campos = acesso irrestrito (24/7).
-- Início > fim representa janela que cruza a meia-noite (ex.: 22:00 -> 06:00).
-- O fim é exclusivo: 08:00-18:00 permite até 17:59:59.
-- ---------------------------------------------------------------------------
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS hora_inicio_acesso TIME NULL;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS hora_fim_acesso    TIME NULL;

ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS ck_usuarios_janela_acesso;
ALTER TABLE usuarios ADD CONSTRAINT ck_usuarios_janela_acesso CHECK (
    (hora_inicio_acesso IS NULL AND hora_fim_acesso IS NULL)
    OR (
        hora_inicio_acesso IS NOT NULL
        AND hora_fim_acesso IS NOT NULL
        AND hora_inicio_acesso <> hora_fim_acesso
    )
);

-- ---------------------------------------------------------------------------
-- REQUISITO 2: reciclagem automática pós-venda
-- A oportunidade original continua em 'Fechado' (preserva receita e KPIs).
-- O worker cria uma NOVA oportunidade em 'Prospecção' ligada pela origem.
-- ---------------------------------------------------------------------------
ALTER TABLE oportunidades
    ADD COLUMN IF NOT EXISTS data_reciclagem_agendada TIMESTAMP WITH TIME ZONE NULL;

ALTER TABLE oportunidades
    ADD COLUMN IF NOT EXISTS status_reciclagem VARCHAR(20) NOT NULL DEFAULT 'nenhum';

ALTER TABLE oportunidades
    ADD COLUMN IF NOT EXISTS oportunidade_origem_id INTEGER NULL
    REFERENCES oportunidades(id) ON DELETE SET NULL;

ALTER TABLE oportunidades DROP CONSTRAINT IF EXISTS ck_oportunidades_status_reciclagem;
ALTER TABLE oportunidades ADD CONSTRAINT ck_oportunidades_status_reciclagem CHECK (
    status_reciclagem IN ('nenhum', 'pendente', 'processado', 'cancelado')
);

-- Agendamento pendente sempre precisa de data
ALTER TABLE oportunidades DROP CONSTRAINT IF EXISTS ck_oportunidades_pendente_com_data;
ALTER TABLE oportunidades ADD CONSTRAINT ck_oportunidades_pendente_com_data CHECK (
    status_reciclagem <> 'pendente' OR data_reciclagem_agendada IS NOT NULL
);

-- Índice parcial: o worker só varre agendamentos pendentes
CREATE INDEX IF NOT EXISTS idx_oportunidades_reciclagem_pendente
    ON oportunidades (data_reciclagem_agendada)
    WHERE status_reciclagem = 'pendente';

CREATE INDEX IF NOT EXISTS idx_oportunidades_origem
    ON oportunidades (oportunidade_origem_id);
