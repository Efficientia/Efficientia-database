BEGIN;

-- ==============================================================================
-- DESFAZIMENTO TOTAL DO AMBIENTE (TEARDOWN COMPLETO EM ORDEM REVERSA)
-- ==============================================================================

-- 1. Executa desfazimento de visões, rotinas e triggers
DROP TRIGGER IF EXISTS tg_impedir_ciclo_anomalia ON sc_operacao.tb_dominio_anomalia;
DROP TRIGGER IF EXISTS tg_outbox_relatorio_viagem ON sc_operacao.tb_relatorio_viagem;
DROP TRIGGER IF EXISTS tg_validar_alocacao_viagem ON sc_operacao.tb_relatorio_viagem;
DROP TRIGGER IF EXISTS tg_audit_relatorio_viagem ON sc_operacao.tb_relatorio_viagem;
DROP TRIGGER IF EXISTS tg_audit_configuracao_operacao ON sc_corporativo.tb_configuracao_operacao;
DROP TRIGGER IF EXISTS tg_audit_usuario ON sc_corporativo.tb_usuario;
DROP TRIGGER IF EXISTS tg_audit_empresa ON sc_corporativo.tb_empresa;

DROP PROCEDURE IF EXISTS sc_auditoria.sp_restaurar_registro_auditoria(UUID);
DROP PROCEDURE IF EXISTS sc_auditoria.sp_registrar_evento_backup(VARCHAR, VARCHAR, VARCHAR, VARCHAR, BIGINT, CHAR, TIMESTAMPTZ, TIMESTAMPTZ, TEXT);
DROP PROCEDURE IF EXISTS sc_auditoria.sp_sincronizar_catalogo_dados(BOOLEAN);
DROP PROCEDURE IF EXISTS sc_operacao.sp_registrar_anomalia(UUID, VARCHAR, VARCHAR, VARCHAR);
DROP PROCEDURE IF EXISTS sc_operacao.sp_aprovar_relatorio(UUID, UUID, BOOLEAN, VARCHAR, TEXT);

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

DROP FUNCTION IF EXISTS sc_auditoria.fn_contagem_linhas_tabelas();
DROP FUNCTION IF EXISTS sc_operacao.fn_obter_subarvore_anomalia(UUID);
DROP FUNCTION IF EXISTS sc_operacao.fn_verificar_ciclo_anomalia();
DROP FUNCTION IF EXISTS sc_operacao.fn_gerar_outbox_relatorio();
DROP FUNCTION IF EXISTS sc_operacao.fn_validar_alocacao_viagem();
DROP FUNCTION IF EXISTS sc_auditoria.fn_registrar_dau();
DROP FUNCTION IF EXISTS sc_auditoria.fn_registrar_auditoria();

-- 2. Remoção de tabelas dependentes (Operação)
DROP TABLE IF EXISTS sc_operacao.tb_outbox_evento CASCADE;
DROP TABLE IF EXISTS sc_operacao.tb_auditoria_analise CASCADE;
DROP TABLE IF EXISTS sc_operacao.tb_anomalia_desembarque CASCADE;
DROP TABLE IF EXISTS sc_operacao.tb_anomalia_embarque CASCADE;
DROP TABLE IF EXISTS sc_operacao.tb_parada_imprevista CASCADE;
DROP TABLE IF EXISTS sc_operacao.tb_relatorio_viagem CASCADE;
DROP TABLE IF EXISTS sc_operacao.tb_dominio_anomalia CASCADE;
DROP TABLE IF EXISTS sc_operacao.tb_dominio_motivo_parada CASCADE;

-- 3. Remoção de tabelas de frota (herança)
DROP TABLE IF EXISTS sc_frota.tb_veiculo_carreta CASCADE;
DROP TABLE IF EXISTS sc_frota.tb_veiculo_cavalo CASCADE;
DROP TABLE IF EXISTS sc_frota.tb_veiculo_base CASCADE;

-- 4. Remoção de tabelas corporativas e auditoria
DROP TABLE IF EXISTS sc_auditoria.tb_historico_backup CASCADE;
DROP TABLE IF EXISTS sc_auditoria.tb_monitoramento_dau CASCADE;
DROP TABLE IF EXISTS sc_auditoria.tb_auditoria_log CASCADE;
DROP TABLE IF EXISTS sc_auditoria.tb_catalogo_dados CASCADE;

DROP TABLE IF EXISTS sc_corporativo.tb_unidade_frigorifica CASCADE;
DROP TABLE IF EXISTS sc_corporativo.tb_fazenda CASCADE;
DROP TABLE IF EXISTS sc_corporativo.tb_usuario CASCADE;
DROP TABLE IF EXISTS sc_corporativo.tb_configuracao_operacao CASCADE;
DROP TABLE IF EXISTS sc_corporativo.tb_empresa CASCADE;
DROP TABLE IF EXISTS sc_corporativo.tb_endereco CASCADE;

-- 5. Remoção de tipos ENUM
DROP TYPE IF EXISTS sc_operacao.ty_status_diario CASCADE;
DROP TYPE IF EXISTS sc_corporativo.ty_categoria_cnh CASCADE;
DROP TYPE IF EXISTS sc_corporativo.ty_nivel_acesso CASCADE;
DROP TYPE IF EXISTS sc_corporativo.ty_tipo_usuario CASCADE;

-- 6. Remoção dos esquemas
DROP SCHEMA IF EXISTS sc_auditoria CASCADE;
DROP SCHEMA IF EXISTS sc_operacao CASCADE;
DROP SCHEMA IF EXISTS sc_frota CASCADE;
DROP SCHEMA IF EXISTS sc_corporativo CASCADE;

COMMIT;
