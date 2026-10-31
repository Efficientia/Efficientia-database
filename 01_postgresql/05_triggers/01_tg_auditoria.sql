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
