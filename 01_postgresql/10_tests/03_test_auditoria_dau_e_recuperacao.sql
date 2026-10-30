-- ==============================================================================
-- SUÍTE DE TESTES 03: TRILHA DE AUDITORIA, DAU E RESTAURAÇÃO CIRÚRGICA
-- ==============================================================================

BEGIN;

DO $$
DECLARE
    v_empresa_id UUID;
    v_usuario_id UUID;
    v_config_id  UUID;
    v_log_id     UUID;
    v_tempo_old  INTEGER;
    v_tempo_rest INTEGER;
BEGIN
    SELECT id INTO v_empresa_id FROM sc_corporativo.tb_empresa LIMIT 1;
    SELECT id INTO v_usuario_id FROM sc_corporativo.tb_usuario WHERE empresa_id = v_empresa_id LIMIT 1;

    -- 1. Teste de registro de Daily Active User (DAU)
    CALL sc_auditoria.fn_registrar_dau(v_usuario_id);

    IF NOT EXISTS (
        SELECT 1 FROM sc_auditoria.tb_monitoramento_dau
         WHERE usuario_id = v_usuario_id AND data_acesso = CURRENT_DATE
    ) THEN
        RAISE EXCEPTION 'Falha no teste: fn_registrar_dau não gravou o acesso diário.';
    END IF;

    -- 2. Teste de auditoria automática em alteração de parâmetros operacionais
    SELECT id, tempo_max_viagem_horas
      INTO v_config_id, v_tempo_old
      FROM sc_corporativo.tb_configuracao_operacao
     WHERE empresa_id = v_empresa_id;

    UPDATE sc_corporativo.tb_configuracao_operacao
       SET tempo_max_viagem_horas = v_tempo_old + 10
     WHERE id = v_config_id;

    SELECT id INTO v_log_id
      FROM sc_auditoria.tb_auditoria_log
     WHERE tabela_afetada = 'sc_corporativo.tb_configuracao_operacao'
       AND operacao = 'UPDATE'
     ORDER BY data_hora DESC
     LIMIT 1;

    IF v_log_id IS NULL THEN
        RAISE EXCEPTION 'Falha no teste: trigger de auditoria não capturou o UPDATE em tb_configuracao_operacao.';
    END IF;

    -- 3. Teste de restauração cirúrgica a partir do log
    CALL sc_auditoria.sp_restaurar_registro_auditoria(v_log_id);

    SELECT tempo_max_viagem_horas
      INTO v_tempo_rest
      FROM sc_corporativo.tb_configuracao_operacao
     WHERE id = v_config_id;

    IF v_tempo_rest <> v_tempo_old THEN
        RAISE EXCEPTION 'Falha no teste: sp_restaurar_registro_auditoria não reverteu para o valor original (esperado: %, obtido: %).',
            v_tempo_old, v_tempo_rest;
    END IF;

    -- 4. Verificação das visualizações analíticas de governança
    PERFORM 1 FROM sc_auditoria.vw_catalogo_dados_completo LIMIT 5;
    PERFORM 1 FROM sc_auditoria.vw_resumo_catalogo_tabelas LIMIT 5;
    PERFORM 1 FROM sc_auditoria.vw_metricas_dau_mau LIMIT 5;
    PERFORM 1 FROM sc_auditoria.vw_status_backups LIMIT 5;

    RAISE NOTICE 'Suíte 03 executada com 100%% de sucesso.';
END $$;

ROLLBACK;
