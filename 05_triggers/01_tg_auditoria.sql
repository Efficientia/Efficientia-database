BEGIN;

-- ==============================================================================
-- 1. TRIGGERS DE AUDITORIA
-- ==============================================================================

-- Auditoria no núcleo transacional (Diários de Rota)
CREATE TRIGGER tg_audit_relatorio_viagem
    AFTER INSERT OR
UPDATE OR
DELETE
ON sc_operacao.tb_relatorio_viagem
    FOR EACH ROW EXECUTE FUNCTION sc_auditoria.fn_registrar_auditoria();

-- Auditoria em parametrizações críticas do sistema (Metas e Prazos)
CREATE TRIGGER tg_audit_configuracao_operacao
    AFTER INSERT OR
UPDATE OR
DELETE
ON sc_corporativo.tb_configuracao_operacao
    FOR EACH ROW EXECUTE FUNCTION sc_auditoria.fn_registrar_auditoria();

-- Auditoria em dados sensíveis de usuários (Alteração de cargos, acessos e status)
CREATE TRIGGER tg_audit_usuario
    AFTER INSERT OR
UPDATE OR
DELETE
ON sc_corporativo.tb_usuario
    FOR EACH ROW EXECUTE FUNCTION sc_auditoria.fn_registrar_auditoria();

-- Auditoria em informações de base das empresas clientes (SaaS)
CREATE TRIGGER tg_audit_empresa
    AFTER INSERT OR
UPDATE OR
DELETE
ON sc_corporativo.tb_empresa
    FOR EACH ROW EXECUTE FUNCTION sc_auditoria.fn_registrar_auditoria();

COMMIT;