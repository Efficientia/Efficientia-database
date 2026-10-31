-- ==============================================================================
-- SUÍTE DE TESTES 02: HIERARQUIA RECURSIVA, ANTI-CICLO E PROPAGAÇÃO EM ÁRVORE
-- ==============================================================================

BEGIN;

DO $$
DECLARE
    v_raiz_id  UUID := 'c1000000-0000-4000-8000-000000000001';
    v_filho_id UUID := 'c2000000-0000-4000-8000-000000000002';
    v_neto_id  UUID := 'c3000000-0000-4000-8000-000000000003';
    v_erro_auto   BOOLEAN := FALSE;
    v_erro_ciclo  BOOLEAN := FALSE;
    v_erro_etapa  BOOLEAN := FALSE;
    v_qtd_sub     INTEGER;
BEGIN
    -- 1. Criação de estrutura hierárquica temporária de teste
    INSERT INTO sc_operacao.tb_dominio_anomalia (id, anomalia_pai_id, tipo_etapa, codigo, descricao, ativo)
    VALUES (v_raiz_id, NULL, 'EMBARQUE', 'teste_raiz', 'Raiz de Teste', TRUE);

    INSERT INTO sc_operacao.tb_dominio_anomalia (id, anomalia_pai_id, tipo_etapa, codigo, descricao, ativo)
    VALUES (v_filho_id, v_raiz_id, 'EMBARQUE', 'teste_filho', 'Filho de Teste', TRUE);

    INSERT INTO sc_operacao.tb_dominio_anomalia (id, anomalia_pai_id, tipo_etapa, codigo, descricao, ativo)
    VALUES (v_neto_id, v_filho_id, 'EMBARQUE', 'teste_neto', 'Neto de Teste', TRUE);

    -- 2. Teste de tentativa de auto-referência direta
    BEGIN
        UPDATE sc_operacao.tb_dominio_anomalia
           SET anomalia_pai_id = v_raiz_id
         WHERE id = v_raiz_id;
    EXCEPTION WHEN SQLSTATE 'P0008' OR check_violation THEN
        v_erro_auto := TRUE;
    END;

    IF NOT v_erro_auto THEN
        RAISE EXCEPTION 'Falha no teste: o banco permitiu autorreferência direta em anomalia.';
    END IF;

    -- 3. Teste de ciclo indireto (Raiz -> Filho -> Neto -> Raiz)
    BEGIN
        UPDATE sc_operacao.tb_dominio_anomalia
           SET anomalia_pai_id = v_neto_id
         WHERE id = v_raiz_id;
    EXCEPTION WHEN SQLSTATE 'P0008' THEN
        v_erro_ciclo := TRUE;
    END;

    IF NOT v_erro_ciclo THEN
        RAISE EXCEPTION 'Falha no teste: trigger anti-ciclo não interceptou ciclo indireto na hierarquia.';
    END IF;

    -- 4. Teste de incompatibilidade de etapa operacional
    BEGIN
        INSERT INTO sc_operacao.tb_dominio_anomalia (anomalia_pai_id, tipo_etapa, codigo, descricao, ativo)
        VALUES (v_raiz_id, 'DESEMBARQUE', 'teste_etapa_invalida', 'Tentativa Cruzada', TRUE);
    EXCEPTION WHEN SQLSTATE 'P0009' THEN
        v_erro_etapa := TRUE;
    END;

    IF NOT v_erro_etapa THEN
        RAISE EXCEPTION 'Falha no teste: permitiu vincular anomalia de DESEMBARQUE a uma raiz de EMBARQUE.';
    END IF;

    -- 5. Validação da função recursiva de extração de subárvore
    SELECT COUNT(*)
      INTO v_qtd_sub
      FROM sc_operacao.fn_obter_subarvore_anomalia(v_raiz_id);

    IF v_qtd_sub <> 3 THEN
        RAISE EXCEPTION 'Falha no teste: fn_obter_subarvore_anomalia retornou % registros (esperado: 3).', v_qtd_sub;
    END IF;

    -- 6. Validação das views hierárquicas
    PERFORM 1 FROM sc_operacao.vw_arvore_dominio_anomalia WHERE id = v_neto_id AND nivel_hierarquia = 3;
    PERFORM 1 FROM sc_operacao.vw_ocorrencias_por_arvore_anomalia WHERE anomalia_id = v_raiz_id;

    RAISE NOTICE 'Suíte 02 executada com 100%% de sucesso.';
END $$;

ROLLBACK;
