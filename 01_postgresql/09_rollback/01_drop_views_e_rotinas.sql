BEGIN;

-- ==============================================================================
-- 1. REMOÇÃO DE TRIGGERS
-- ==============================================================================
DROP TRIGGER IF EXISTS tg_impedir_ciclo_anomalia ON sc_operacao.tb_dominio_anomalia;
DROP TRIGGER IF EXISTS tg_outbox_relatorio_viagem ON sc_operacao.tb_relatorio_viagem;
DROP TRIGGER IF EXISTS tg_validar_alocacao_viagem ON sc_operacao.tb_relatorio_viagem;
DROP TRIGGER IF EXISTS tg_audit_relatorio_viagem ON sc_operacao.tb_relatorio_viagem;
DROP TRIGGER IF EXISTS tg_audit_configuracao_operacao ON sc_corporativo.tb_configuracao_operacao;
DROP TRIGGER IF EXISTS tg_audit_usuario ON sc_corporativo.tb_usuario;
DROP TRIGGER IF EXISTS tg_audit_empresa ON sc_corporativo.tb_empresa;

-- ==============================================================================
-- 2. REMOÇÃO DE PROCEDURES
-- ==============================================================================
DROP PROCEDURE IF EXISTS sc_auditoria.sp_restaurar_registro_auditoria(UUID);
DROP PROCEDURE IF EXISTS sc_auditoria.sp_registrar_evento_backup(VARCHAR, VARCHAR, VARCHAR, VARCHAR, BIGINT, CHAR, TIMESTAMPTZ, TIMESTAMPTZ, TEXT);
DROP PROCEDURE IF EXISTS sc_auditoria.sp_sincronizar_catalogo_dados(BOOLEAN);
DROP PROCEDURE IF EXISTS sc_operacao.sp_registrar_anomalia(UUID, VARCHAR, VARCHAR, VARCHAR);
DROP PROCEDURE IF EXISTS sc_operacao.sp_aprovar_relatorio(UUID, UUID, BOOLEAN, VARCHAR, TEXT);

-- ==============================================================================
-- 3. REMOÇÃO DE VIEWS MATERIALIZADAS E VIEWS COMUNS
-- ==============================================================================
DROP MATERIALIZED VIEW IF EXISTS sc_operacao.mv_analise_mortalidade_mensal CASCADE;

DROP VIEW IF EXISTS sc_auditoria.vw_status_backups CASCADE;
DROP VIEW IF EXISTS sc_auditoria.vw_dau_por_empresa CASCADE;
DROP VIEW IF EXISTS sc_auditoria.vw_metricas_dau_mau CASCADE;
DROP VIEW IF EXISTS sc_auditoria.vw_resumo_catalogo_tabelas CASCADE;
DROP VIEW IF EXISTS sc_auditoria.vw_catalogo_dados_completo CASCADE;
DROP VIEW IF EXISTS sc_operacao.vw_ocorrencias_por_arvore_anomalia CASCADE;
DROP VIEW IF EXISTS sc_operacao.vw_arvore_dominio_anomalia CASCADE;
DROP VIEW IF EXISTS sc_operacao.vw_fato_transporte_animal CASCADE;
DROP VIEW IF EXISTS sc_corporativo.vw_dim_localidade CASCADE;
DROP VIEW IF EXISTS sc_frota.vw_dim_frota CASCADE;
DROP VIEW IF EXISTS sc_corporativo.vw_dim_colaborador CASCADE;
DROP VIEW IF EXISTS sc_corporativo.vw_dim_empresa CASCADE;

-- ==============================================================================
-- 4. REMOÇÃO DE FUNÇÕES
-- ==============================================================================
DROP FUNCTION IF EXISTS sc_auditoria.fn_contagem_linhas_tabelas();
DROP FUNCTION IF EXISTS sc_operacao.fn_obter_subarvore_anomalia(UUID);
DROP FUNCTION IF EXISTS sc_operacao.fn_verificar_ciclo_anomalia();
DROP FUNCTION IF EXISTS sc_operacao.fn_gerar_outbox_relatorio();
DROP FUNCTION IF EXISTS sc_operacao.fn_validar_alocacao_viagem();
DROP FUNCTION IF EXISTS sc_auditoria.fn_registrar_dau();
DROP FUNCTION IF EXISTS sc_auditoria.fn_registrar_auditoria();

COMMIT;
