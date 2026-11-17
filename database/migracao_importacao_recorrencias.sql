-- SANDRO CRM - importação de planilhas, CPF/CNPJ e recorrências
-- Idempotente e só ADITIVA (colunas e tabelas novas): a versão anterior da API
-- continua funcionando com o banco migrado. Requer as migrações anteriores.

-- 1) CPF/CNPJ do cliente, sem pontuação, único por empresa:
--    CPF = 11 dígitos; CNPJ = 14 posições, as 12 primeiras podem ter letras
--    (CNPJ alfanumérico, emitido pela Receita desde julho/2026) e as 2 últimas
--    (dígitos verificadores) são sempre números.
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS documento VARCHAR(14) NULL;

ALTER TABLE clientes DROP CONSTRAINT IF EXISTS ck_clientes_documento;
ALTER TABLE clientes ADD CONSTRAINT ck_clientes_documento
    CHECK (documento IS NULL OR documento ~ '^([0-9]{11}|[0-9A-Z]{12}[0-9]{2})$');

-- Mesmo documento pode existir em empresas diferentes (cada uma tem seus clientes)
CREATE UNIQUE INDEX IF NOT EXISTS uq_clientes_empresa_documento
    ON clientes (empresa_id, documento) WHERE documento IS NOT NULL;

-- 2) Regras de recorrência ("toda segunda", "todo dia 5")
CREATE TABLE IF NOT EXISTS recorrencias (
    id               SERIAL PRIMARY KEY,
    empresa_id       INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    -- A regra é dado do cliente: some junto com ele (LGPD)
    cliente_id       INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    -- lembrete = cria um follow-up (tarefa); oportunidade = cria um card no funil
    tipo             VARCHAR(20) NOT NULL CHECK (tipo IN ('lembrete', 'oportunidade')),
    titulo           VARCHAR(150) NOT NULL CHECK (length(btrim(titulo)) > 0),
    valor            NUMERIC(12,2) NULL CHECK (valor IS NULL OR valor >= 0),
    notas            TEXT NULL CHECK (notas IS NULL OR length(notas) <= 2000),
    frequencia       VARCHAR(10) NOT NULL CHECK (frequencia IN ('semanal', 'mensal')),
    dia_semana       SMALLINT NULL CHECK (dia_semana BETWEEN 1 AND 7),  -- ISO: 1 = segunda
    dia_mes          SMALLINT NULL CHECK (dia_mes BETWEEN 1 AND 31),    -- 31 = último dia em meses curtos
    -- Próxima data a gerar, no calendário da empresa (TZ_EMPRESA)
    proxima_execucao DATE NOT NULL,
    ativo            BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por       INTEGER NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    criado_em        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    atualizado_em    TIMESTAMP WITH TIME ZONE NULL,
    CONSTRAINT ck_recorrencias_dia CHECK (
        (frequencia = 'semanal' AND dia_semana IS NOT NULL AND dia_mes IS NULL)
        OR (frequencia = 'mensal' AND dia_mes IS NOT NULL AND dia_semana IS NULL)
    )
);

-- O worker só varre regras ativas e vencidas
CREATE INDEX IF NOT EXISTS idx_recorrencias_vencidas
    ON recorrencias (proxima_execucao) WHERE ativo;
CREATE INDEX IF NOT EXISTS idx_recorrencias_empresa_cliente
    ON recorrencias (empresa_id, cliente_id);

-- 3) Uma linha por (regra, data): trava contra duplicata mesmo com duas
--    execuções do worker ao mesmo tempo ou reprocessamento manual
CREATE TABLE IF NOT EXISTS recorrencia_execucoes (
    id              SERIAL PRIMARY KEY,
    recorrencia_id  INTEGER NOT NULL REFERENCES recorrencias(id) ON DELETE CASCADE,
    empresa_id      INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    data_referencia DATE NOT NULL,
    tarefa_id       INTEGER NULL REFERENCES tarefas(id) ON DELETE SET NULL,
    oportunidade_id INTEGER NULL REFERENCES oportunidades(id) ON DELETE SET NULL,
    executado_em    TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_recorrencia_execucoes UNIQUE (recorrencia_id, data_referencia)
);

-- Rastreio: de qual regra veio cada follow-up / oportunidade
ALTER TABLE tarefas ADD COLUMN IF NOT EXISTS recorrencia_id INTEGER NULL
    REFERENCES recorrencias(id) ON DELETE SET NULL;
ALTER TABLE oportunidades ADD COLUMN IF NOT EXISTS recorrencia_id INTEGER NULL
    REFERENCES recorrencias(id) ON DELETE SET NULL;

-- 4) Registro das importações (quem, quando, quantas linhas, hash do arquivo).
--    Não guarda o conteúdo da planilha.
CREATE TABLE IF NOT EXISTS importacoes (
    id                   SERIAL PRIMARY KEY,
    empresa_id           INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    usuario_id           INTEGER NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    arquivo_nome         VARCHAR(120) NOT NULL,
    formato              VARCHAR(5) NOT NULL CHECK (formato IN ('csv', 'xlsx')),
    sha256               CHAR(64) NOT NULL,
    linhas               INTEGER NOT NULL CHECK (linhas >= 0),
    clientes_criados     INTEGER NOT NULL CHECK (clientes_criados >= 0),
    recorrencias_criadas INTEGER NOT NULL CHECK (recorrencias_criadas >= 0),
    criado_em            TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_importacoes_empresa_data ON importacoes (empresa_id, criado_em DESC);

-- Mesmo bloqueio da API REST do Supabase aplicado às outras tabelas
ALTER TABLE recorrencias          ENABLE ROW LEVEL SECURITY;
ALTER TABLE recorrencia_execucoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE importacoes           ENABLE ROW LEVEL SECURITY;
