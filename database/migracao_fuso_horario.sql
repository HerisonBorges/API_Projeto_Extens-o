-- SANDRO CRM - colunas de data/hora passam a guardar o fuso (TIMESTAMPTZ)
--
-- Por quê: estas colunas eram TIMESTAMP sem fuso, gravadas com NOW() numa
-- sessão em UTC. Converter para o horário da empresa com AT TIME ZONE sobre
-- um valor sem fuso desloca o horário no sentido errado (+3h em vez de -3h
-- em São Paulo), e a API devolvia datas sem fuso, lidas como hora local pelo
-- navegador.
--
-- Os valores existentes são interpretados como UTC (como foram gravados): o
-- instante não muda, só passa a carregar o fuso. Idempotente.

DO $$
DECLARE
    alvo RECORD;
BEGIN
    FOR alvo IN
        SELECT c.table_name, c.column_name
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.data_type = 'timestamp without time zone'
          AND (c.table_name, c.column_name) IN (
              ('oportunidades', 'criado_em'),
              ('oportunidades', 'etapa_atualizada_em'),
              ('clientes', 'criado_em'),
              ('empresas', 'criado_em'),
              ('usuarios', 'criado_em')
          )
    LOOP
        EXECUTE format(
            'ALTER TABLE public.%I ALTER COLUMN %I TYPE TIMESTAMP WITH TIME ZONE USING %I AT TIME ZONE ''UTC''',
            alvo.table_name, alvo.column_name, alvo.column_name
        );
        RAISE NOTICE 'Convertida: %.%', alvo.table_name, alvo.column_name;
    END LOOP;
END $$;
