-- SANDRO CRM - edição de clientes: quem alterou por último e quando
-- Idempotente. Requer as migrações anteriores.

ALTER TABLE clientes ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMP WITH TIME ZONE NULL;
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS atualizado_por INTEGER NULL
    REFERENCES usuarios(id) ON DELETE SET NULL;

-- Status aceitos pela aplicação (os dados atuais já seguem estes valores)
ALTER TABLE clientes DROP CONSTRAINT IF EXISTS ck_clientes_status;
ALTER TABLE clientes ADD CONSTRAINT ck_clientes_status
    CHECK (status IN ('Lead', 'Cliente', 'Inativo'));
