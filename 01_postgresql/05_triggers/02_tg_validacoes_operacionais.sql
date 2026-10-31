BEGIN;

-- ==============================================================================
-- 1. TRIGGERS DE VALIDAÇÃO
-- ==============================================================================

-- Validação de alocação de frota e motorista disparada apenas ao inserir ou alterar condutor/veículos
DROP TRIGGER IF EXISTS tg_validar_alocacao_viagem ON sc_operacao.tb_relatorio_viagem;
CREATE TRIGGER tg_validar_alocacao_viagem
    BEFORE INSERT OR UPDATE OF motorista_id, cavalo_id, carreta_id ON sc_operacao.tb_relatorio_viagem
    FOR EACH ROW EXECUTE FUNCTION sc_operacao.fn_validar_alocacao_viagem();

-- ==============================================================================
-- 2. TRIGGER DE MENSAGERIA E INTEGRAÇÃO (OUTBOX PATTERN COM REDIS)
-- ==============================================================================

-- Disparo transacional de eventos para captura pelo worker/relay do Redis
DROP TRIGGER IF EXISTS tg_outbox_relatorio_viagem ON sc_operacao.tb_relatorio_viagem;
CREATE TRIGGER tg_outbox_relatorio_viagem
    AFTER INSERT OR UPDATE OF status ON sc_operacao.tb_relatorio_viagem
    FOR EACH ROW EXECUTE FUNCTION sc_operacao.fn_gerar_outbox_relatorio();

COMMIT;