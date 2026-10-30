BEGIN;

-- ==============================================================================
-- TRIGGER DE PROTEÇÃO CONTRA CICLOS EM HIERARQUIA DE ANOMALIAS
-- ==============================================================================
DROP TRIGGER IF EXISTS tg_impedir_ciclo_anomalia ON sc_operacao.tb_dominio_anomalia;
CREATE TRIGGER tg_impedir_ciclo_anomalia
    BEFORE INSERT OR UPDATE OF anomalia_pai_id, tipo_etapa ON sc_operacao.tb_dominio_anomalia
    FOR EACH ROW EXECUTE FUNCTION sc_operacao.fn_verificar_ciclo_anomalia();

COMMIT;
