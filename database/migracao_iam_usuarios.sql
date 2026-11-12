-- SANDRO CRM - IAM: ciclo de vida de contas, sessões, bloqueio e auditoria
-- Idempotente. Requer as migrações anteriores.

-- Contas são desativadas, nunca apagadas pela aplicação (rastreabilidade)
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ativo BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS desativado_em TIMESTAMP WITH TIME ZONE NULL;

-- Senha temporária (criação, redefinição e reativação): troca obrigatória
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS deve_trocar_senha BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS senha_temporaria_expira_em TIMESTAMP WITH TIME ZONE NULL;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS senha_alterada_em TIMESTAMP WITH TIME ZONE NULL;

-- Versão do token: incrementar encerra TODAS as sessões abertas do usuário
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS token_versao INTEGER NOT NULL DEFAULT 1;

-- Proteção contra força bruta no login
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS tentativas_falhas INTEGER NOT NULL DEFAULT 0;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS bloqueado_ate TIMESTAMP WITH TIME ZONE NULL;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS ultimo_login_em TIMESTAMP WITH TIME ZONE NULL;

-- E-mail único sem diferenciar maiúsculas (Ana@x.com = ana@x.com)
CREATE UNIQUE INDEX IF NOT EXISTS uq_usuarios_email_lower ON usuarios (lower(email));

-- Trilha de auditoria de IAM. NUNCA guarda senhas, hashes ou tokens.
CREATE TABLE IF NOT EXISTS auditoria_usuarios (
    id          SERIAL PRIMARY KEY,
    empresa_id  INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    ator_id     INTEGER NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    alvo_id     INTEGER NULL REFERENCES usuarios(id) ON DELETE SET NULL,
    acao        VARCHAR(40) NOT NULL CHECK (acao IN (
                    'usuario_criado', 'usuario_alterado', 'perfil_alterado',
                    'senha_redefinida', 'senha_alterada', 'usuario_desativado',
                    'usuario_reativado', 'login_bloqueado'
                )),
    detalhes    JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip          VARCHAR(64) NULL,
    criado_em   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_auditoria_empresa_data ON auditoria_usuarios (empresa_id, criado_em DESC);

ALTER TABLE auditoria_usuarios ENABLE ROW LEVEL SECURITY;
