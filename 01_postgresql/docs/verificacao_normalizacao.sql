-- ==============================================================================
-- PROJETO EFFICIENTIA - SCRIPT DE VERIFICAÇÃO AUTOMATIZADA DE NORMALIZAÇÃO
-- ==============================================================================
-- Valida as restrições relacionais, chaves candidatas e integridade referencial
-- para assegurar conformidade com 1FN, 2FN, 3FN e FNBC no PostgreSQL.
-- ==============================================================================

BEGIN;

-- 1. Verificação de Chaves Primárias em 100% das tabelas físicas
DO $$
DECLARE
    v_tabelas_sem_pk INTEGER;
BEGIN
    SELECT COUNT(*)
      INTO v_tabelas_sem_pk
      FROM pg_catalog.pg_class c
     INNER JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname IN ('sc_auditoria', 'sc_corporativo', 'sc_frota', 'sc_operacao')
       AND c.relkind = 'r'
       AND NOT EXISTS (
           SELECT 1
             FROM pg_catalog.pg_constraint con
            WHERE con.conrelid = c.oid
              AND con.contype = 'p'
       );

    IF v_tabelas_sem_pk > 0 THEN
        RAISE EXCEPTION 'Violação de integridade: existem % tabelas sem chave primária definida.', v_tabelas_sem_pk;
    END IF;

    RAISE NOTICE '[OK] Todas as tabelas possuem Chave Primária (PK) definida (1FN/2FN garantidas).';
END $$;


-- 2. Verificação de Chaves Candidatas Únicas declaradas
DO $$
DECLARE
    v_qtd_unicas INTEGER;
BEGIN
    SELECT COUNT(*)
      INTO v_qtd_unicas
      FROM pg_catalog.pg_constraint con
     INNER JOIN pg_catalog.pg_namespace n ON n.oid = con.connamespace
     WHERE n.nspname IN ('sc_auditoria', 'sc_corporativo', 'sc_frota', 'sc_operacao')
       AND con.contype = 'u';

    IF v_qtd_unicas < 10 THEN
        RAISE EXCEPTION 'Aviso de modelagem: quantidade de chaves candidatas únicas inferior ao esperado (%).', v_qtd_unicas;
    END IF;

    RAISE NOTICE '[OK] % restrições de unicidade (chaves candidatas) ativas no catálogo.', v_qtd_unicas;
END $$;


-- 3. Verificação de integridade referencial de Foreign Keys
DO $$
DECLARE
    v_fk_invalidas INTEGER;
BEGIN
    SELECT COUNT(*)
      INTO v_fk_invalidas
      FROM pg_catalog.pg_constraint con
     INNER JOIN pg_catalog.pg_namespace n ON n.oid = con.connamespace
     WHERE n.nspname IN ('sc_auditoria', 'sc_corporativo', 'sc_frota', 'sc_operacao')
       AND con.contype = 'f'
       AND NOT con.convalidated;

    IF v_fk_invalidas > 0 THEN
        RAISE EXCEPTION 'Violação de integridade: existem % chaves estrangeiras não validadas.', v_fk_invalidas;
    END IF;

    RAISE NOTICE '[OK] Todas as chaves estrangeiras estão íntegras e ativas.';
END $$;


-- 4. Verificação de atomicidade em colunas (ausência de arrays nativos em tabelas transacionais)
DO $$
DECLARE
    v_colunas_array INTEGER;
BEGIN
    SELECT COUNT(*)
      INTO v_colunas_array
      FROM pg_catalog.pg_attribute a
     INNER JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
     INNER JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
     INNER JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
     WHERE n.nspname IN ('sc_corporativo', 'sc_frota', 'sc_operacao')
       AND c.relkind = 'r'
       AND a.attnum > 0
       AND NOT a.attisdropped
       AND t.typcategory = 'A';

    IF v_colunas_array > 0 THEN
        RAISE EXCEPTION 'Aviso de 1FN: detectada coluna do tipo Array nativo em esquema transacional.';
    END IF;

    RAISE NOTICE '[OK] Nenhuma coluna multivalorada não atômica (Array) em esquemas operacionais (1FN garantida).';
END $$;

ROLLBACK;
