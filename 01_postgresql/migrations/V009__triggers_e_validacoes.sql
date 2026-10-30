-- ==============================================================================
-- EFFICIENTIA - MIGRATION V009: GATILHOS E VALIDATION RULES
-- ==============================================================================

BEGIN;

-- ==============================================================================
-- 1. TRIGGERS DE AUDITORIA
-- ==============================================================================

-- Auditoria no núcleo transacional (Diários de Rota)
DROP TRIGGER IF EXISTS tg_audit_relatorio_viagem ON sc_operacao.tb_relatorio_viagem;
CREATE TRIGGER tg_audit_relatorio_viagem
    AFTER INSERT OR
UPDATE OR
DELETE
ON sc_operacao.tb_relatorio_viagem
    FOR EACH ROW EXECUTE FUNCTION sc_auditoria.fn_registrar_auditoria();

-- Auditoria em parametrizações críticas do sistema (Metas e Prazos)
DROP TRIGGER IF EXISTS tg_audit_configuracao_operacao ON sc_corporativo.tb_configuracao_operacao;
CREATE TRIGGER tg_audit_configuracao_operacao
    AFTER INSERT OR
UPDATE OR
DELETE
ON sc_corporativo.tb_configuracao_operacao
    FOR EACH ROW EXECUTE FUNCTION sc_auditoria.fn_registrar_auditoria();

-- Auditoria em dados sensíveis de usuários (Alteração de cargos, acessos e status)
DROP TRIGGER IF EXISTS tg_audit_usuario ON sc_corporativo.tb_usuario;
CREATE TRIGGER tg_audit_usuario
    AFTER INSERT OR
UPDATE OR
DELETE
ON sc_corporativo.tb_usuario
    FOR EACH ROW EXECUTE FUNCTION sc_auditoria.fn_registrar_auditoria();

-- Auditoria em informações de base das empresas clientes
DROP TRIGGER IF EXISTS tg_audit_empresa ON sc_corporativo.tb_empresa;
CREATE TRIGGER tg_audit_empresa
    AFTER INSERT OR
UPDATE OR
DELETE
ON sc_corporativo.tb_empresa
    FOR EACH ROW EXECUTE FUNCTION sc_auditoria.fn_registrar_auditoria();

COMMIT;


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

BEGIN;

-- ==============================================================================
-- TRIGGER DE PROTEÇÃO CONTRA CICLOS EM HIERARQUIA DE ANOMALIAS
-- ==============================================================================
DROP TRIGGER IF EXISTS tg_impedir_ciclo_anomalia ON sc_operacao.tb_dominio_anomalia;
CREATE TRIGGER tg_impedir_ciclo_anomalia
    BEFORE INSERT OR UPDATE OF anomalia_pai_id, tipo_etapa ON sc_operacao.tb_dominio_anomalia
    FOR EACH ROW EXECUTE FUNCTION sc_operacao.fn_verificar_ciclo_anomalia();

COMMIT;

