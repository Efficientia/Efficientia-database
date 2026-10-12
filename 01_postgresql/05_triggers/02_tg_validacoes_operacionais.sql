BEGIN;

-- ==============================================================================
-- 1. TRIGGERS DE VALIDA├ç├âO
-- ==============================================================================

-- Valida├º├úo de aloca├º├úo de frota e motorista antes de registrar ou alterar uma viagem
CREATE TRIGGER tg_validar_alocacao_viagem
    BEFORE INSERT OR
UPDATE ON sc_operacao.tb_relatorio_viagem
    FOR EACH ROW EXECUTE FUNCTION sc_operacao.fn_validar_alocacao_viagem();

COMMIT;
