BEGIN;

-- ==============================================================================
-- 1. ÍNDICES DE ISOLAMENTO MULTI-TENANT
-- ==============================================================================
CREATE INDEX idx_usuario_empresa ON sc_corporativo.tb_usuario (empresa_id);
CREATE INDEX idx_veiculo_base_empresa ON sc_frota.tb_veiculo_base (empresa_id);
CREATE INDEX idx_fazenda_empresa ON sc_corporativo.tb_fazenda (empresa_id);
CREATE INDEX idx_unidade_frigorifica_empresa ON sc_corporativo.tb_unidade_frigorifica (empresa_id);
CREATE INDEX idx_relatorio_viagem_empresa ON sc_operacao.tb_relatorio_viagem (empresa_id);

-- ==============================================================================
-- 2. ÍNDICES DE RELACIONAMENTO (FOREIGN KEYS)
-- ==============================================================================
-- [sc_corporativo]
CREATE INDEX idx_empresa_endereco ON sc_corporativo.tb_empresa (endereco_id);
CREATE INDEX idx_fazenda_pecuarista ON sc_corporativo.tb_fazenda (pecuarista_id);
CREATE INDEX idx_fazenda_endereco ON sc_corporativo.tb_fazenda (endereco_id);
CREATE INDEX idx_unidade_analista ON sc_corporativo.tb_unidade_frigorifica (analista_id);
CREATE INDEX idx_unidade_endereco ON sc_corporativo.tb_unidade_frigorifica (endereco_id);

-- [sc_operacao]
CREATE INDEX idx_relatorio_fazenda ON sc_operacao.tb_relatorio_viagem (fazenda_id);
CREATE INDEX idx_relatorio_motorista ON sc_operacao.tb_relatorio_viagem (motorista_id);
CREATE INDEX idx_relatorio_manobrista ON sc_operacao.tb_relatorio_viagem (manobrista_id);
CREATE INDEX idx_relatorio_curraleiro ON sc_operacao.tb_relatorio_viagem (curraleiro_id);
CREATE INDEX idx_relatorio_cavalo ON sc_operacao.tb_relatorio_viagem (cavalo_id);
CREATE INDEX idx_relatorio_carreta ON sc_operacao.tb_relatorio_viagem (carreta_id);

-- [sc_operacao]
CREATE INDEX idx_parada_relatorio ON sc_operacao.tb_parada_imprevista (relatorio_id);
CREATE INDEX idx_parada_dominio ON sc_operacao.tb_parada_imprevista (dominio_parada_id);

CREATE INDEX idx_ano_emb_relatorio ON sc_operacao.tb_anomalia_embarque (relatorio_id);
CREATE INDEX idx_ano_emb_dominio ON sc_operacao.tb_anomalia_embarque (dominio_anomalia_id);

CREATE INDEX idx_ano_des_relatorio ON sc_operacao.tb_anomalia_desembarque (relatorio_id);
CREATE INDEX idx_ano_des_dominio ON sc_operacao.tb_anomalia_desembarque (dominio_anomalia_id);

CREATE INDEX idx_aud_analise_relatorio ON sc_operacao.tb_auditoria_analise (relatorio_id);
CREATE INDEX idx_aud_analise_analista ON sc_operacao.tb_auditoria_analise (analista_id);

-- [sc_auditoria]
CREATE INDEX idx_monitoramento_dau_usuario ON sc_auditoria.tb_monitoramento_dau (usuario_id);

-- ==============================================================================
-- 3. ÍNDICES DE PERFORMANCE PARA BUSCAS E FILTROS FREQUENTES
-- ==============================================================================
CREATE INDEX idx_usuario_cpf ON sc_corporativo.tb_usuario (cpf);
CREATE INDEX idx_veiculo_base_placa ON sc_frota.tb_veiculo_base (placa);
CREATE INDEX idx_relatorio_gta ON sc_operacao.tb_relatorio_viagem (numero_gta);
CREATE INDEX idx_relatorio_pendente_aprovado
    ON sc_operacao.tb_relatorio_viagem (status) WHERE status IN ('pendente', 'aprovado');

COMMIT;