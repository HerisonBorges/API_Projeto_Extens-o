-- SANDRO CRM - papel de banco restrito para o worker de reciclagem (GitHub Actions)
--
-- Por quê: os secrets do Actions ficam fora do seu controle direto. Com este
-- papel, um vazamento expõe só a tabela oportunidades, sem DELETE e sem acesso
-- a clientes, usuários (hashes de senha) ou interações.
--
-- Como usar (SQL Editor do Supabase, uma vez por banco):
--   1. Rode este arquivo inteiro. É idempotente.
--   2. Defina a senha SEPARADAMENTE (nunca commite a senha):
--        ALTER ROLE sandro_worker PASSWORD '<senha-longa-gerada>';
--   3. Nos secrets do Actions use DB_USER=sandro_worker.<ref-do-projeto>
--      (formato do Session pooler) e a senha do passo 2.
--
-- Não altera a API, que continua usando o próprio usuário.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sandro_worker') THEN
        CREATE ROLE sandro_worker LOGIN NOINHERIT;
    END IF;
END $$;

-- Proteções do papel
ALTER ROLE sandro_worker CONNECTION LIMIT 3;
ALTER ROLE sandro_worker SET statement_timeout = '60s';
ALTER ROLE sandro_worker SET idle_in_transaction_session_timeout = '60s';

DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO sandro_worker', current_database());
END $$;

GRANT USAGE ON SCHEMA public TO sandro_worker;

-- Só o necessário: listar vencidas, travar (FOR UPDATE), marcar e criar a nova
REVOKE ALL ON public.oportunidades FROM sandro_worker;
GRANT SELECT, INSERT, UPDATE ON public.oportunidades TO sandro_worker;

DO $$
BEGIN
    EXECUTE format('GRANT USAGE ON SEQUENCE %s TO sandro_worker',
                   pg_get_serial_sequence('public.oportunidades', 'id'));
END $$;

-- RLS está ligado (migração anterior) e bloqueia papéis que não são donos da
-- tabela. Esta política libera as linhas só para o worker.
DROP POLICY IF EXISTS worker_reciclagem ON public.oportunidades;
CREATE POLICY worker_reciclagem ON public.oportunidades
    FOR ALL TO sandro_worker
    USING (true)
    WITH CHECK (true);
