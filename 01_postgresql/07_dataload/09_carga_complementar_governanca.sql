-- ============================================================================
-- EFFICIENTIA - DATALOAD COMPLEMENTAR: GOVERNANÇA LGPD, HIERARQUIA E BACKUPS
-- ============================================================================

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

BEGIN;

-- ==============================================================================
-- 1. CATALOGAÇÃO DAS NOVAS TABELAS E COLUNAS DE GOVERNANÇA
-- ==============================================================================
INSERT INTO sc_auditoria.tb_catalogo_dados
(esquema_nome, tabela_nome, coluna_nome, descricao, regra_negocio_critica, nivel_acesso_leitura, nivel_acesso_escrita, dado_pessoal_lgpd)
VALUES
('sc_auditoria', 'tb_catalogo_dados', 'dado_pessoal_lgpd', 'Indicador booleano de atributo sujeito à Lei Geral de Proteção de Dados (LGPD).',
 'Classificação obrigatória de dados pessoais e sensíveis.', 'auditoria', 'administrativo', FALSE),
('sc_operacao', 'tb_dominio_anomalia', 'anomalia_pai_id', 'Autorreferência para categoria superior na árvore de anomalias.',
 'Validado contra ciclos via trigger recursiva antes da persistência.', 'conducao', 'administrativo', FALSE),
('sc_auditoria', 'tb_historico_backup', 'id', 'Identificador único do evento de cópia de segurança ou restauração.',
 'Chave primária do histórico operacional.', 'auditoria', 'administrativo', FALSE),
('sc_auditoria', 'tb_historico_backup', 'operacao', 'Tipo de operação executada (BACKUP, RESTORE ou RESTORE_AUDITORIA).',
 'Restrito por CHECK constraint.', 'auditoria', 'administrativo', FALSE),
('sc_auditoria', 'tb_historico_backup', 'status', 'Resultado final da execução (SUCESSO ou FALHA).',
 'Base para cálculo de conformidade de RPO.', 'auditoria', 'administrativo', FALSE),
('sc_auditoria', 'tb_historico_backup', 'nome_banco', 'Nome do banco de dados alvo da rotina.',
 'Identificação de ambiente.', 'auditoria', 'administrativo', FALSE),
('sc_auditoria', 'tb_historico_backup', 'arquivo_dump', 'Nome do artefato binário (.dump) ou referência ao log restaurado.',
 'Rastreabilidade física do arquivo.', 'auditoria', 'administrativo', FALSE),
('sc_auditoria', 'tb_historico_backup', 'tamanho_bytes', 'Volume do arquivo gerado em bytes.',
 'Monitoramento de crescimento volumétrico.', 'auditoria', 'administrativo', FALSE),
('sc_auditoria', 'tb_historico_backup', 'checksum_sha256', 'Resumo criptográfico SHA-256 do arquivo de backup.',
 'Verificação de integridade antes de restauração.', 'auditoria', 'administrativo', FALSE),
('sc_auditoria', 'tb_historico_backup', 'iniciado_em', 'Carimbo de tempo do início da rotina.',
 'Cálculo de janela de RTO.', 'auditoria', 'administrativo', FALSE),
('sc_auditoria', 'tb_historico_backup', 'finalizado_em', 'Carimbo de tempo da conclusão da rotina.',
 'Deve ser maior ou igual a iniciado_em.', 'auditoria', 'administrativo', FALSE),
('sc_auditoria', 'tb_historico_backup', 'executado_por', ' Papel de banco responsável pela execução.',
 'Rastreabilidade de operação privilegiada.', 'auditoria', 'administrativo', FALSE),
('sc_auditoria', 'tb_historico_backup', 'mensagem_erro', 'Diagnóstico capturado em caso de falha na rotina.',
 'Insumo para resposta a incidentes.', 'auditoria', 'administrativo', FALSE)
ON CONFLICT (esquema_nome, tabela_nome, coluna_nome) DO UPDATE SET
    descricao             = EXCLUDED.descricao,
    regra_negocio_critica = EXCLUDED.regra_negocio_critica,
    nivel_acesso_leitura  = EXCLUDED.nivel_acesso_leitura,
    nivel_acesso_escrita  = EXCLUDED.nivel_acesso_escrita,
    dado_pessoal_lgpd     = EXCLUDED.dado_pessoal_lgpd,
    atualizado_em         = CURRENT_TIMESTAMP;


-- ==============================================================================
-- 2. MARCAÇÃO DE ATRIBUTOS PESSOAIS / SENSÍVEIS (LGPD)
-- ==============================================================================
UPDATE sc_auditoria.tb_catalogo_dados
   SET dado_pessoal_lgpd = TRUE,
       atualizado_em     = CURRENT_TIMESTAMP
 WHERE (esquema_nome = 'sc_corporativo' AND tabela_nome = 'tb_usuario'
        AND coluna_nome IN ('cpf', 'cnh_numero', 'nome_completo', 'data_nascimento', 'email', 'telefone', 'senha_hash', 'url_assinatura_geral'))
    OR (esquema_nome = 'sc_operacao' AND tabela_nome = 'tb_relatorio_viagem'
        AND coluna_nome IN ('url_assinatura_pecuarista', 'url_assinatura_motorista', 'url_assinatura_manobrista', 'url_assinatura_curraleiro'))
    OR (esquema_nome = 'sc_auditoria' AND tabela_nome = 'tb_auditoria_log'
        AND coluna_nome IN ('dados_antigos', 'dados_novos'));


-- ==============================================================================
-- 3. ÁRVORE HIERÁRQUICA DE 3 NÍVEIS NO DOMÍNIO DE ANOMALIAS
-- ==============================================================================
-- Nível 1: Raízes por etapa operacional
INSERT INTO sc_operacao.tb_dominio_anomalia (id, anomalia_pai_id, tipo_etapa, codigo, descricao, ativo) VALUES
('a1000000-0000-4000-8000-000000000001', NULL, 'EMBARQUE', 'raiz_embarque', 'Conformidade de bem-estar e operação no embarque', TRUE),
('b1000000-0000-4000-8000-000000000001', NULL, 'DESEMBARQUE', 'raiz_desembarque', 'Conformidade de bem-estar e recepção no desembarque', TRUE)
ON CONFLICT (tipo_etapa, codigo) DO UPDATE SET
    descricao       = EXCLUDED.descricao,
    anomalia_pai_id = EXCLUDED.anomalia_pai_id;

-- Nível 2: Categorias intermediárias vinculadas às raízes
INSERT INTO sc_operacao.tb_dominio_anomalia (id, anomalia_pai_id, tipo_etapa, codigo, descricao, ativo) VALUES
('a2000000-0000-4000-8000-000000000001', 'a1000000-0000-4000-8000-000000000001', 'EMBARQUE', 'cat_condicao_fisica_animal', 'Condição física e sanitária prévia do animal', TRUE),
('a2000000-0000-4000-8000-000000000002', 'a1000000-0000-4000-8000-000000000001', 'EMBARQUE', 'cat_manejo_conducao_embarque', 'Falhas de manejo e condução na origem', TRUE),
('a2000000-0000-4000-8000-000000000003', 'a1000000-0000-4000-8000-000000000001', 'EMBARQUE', 'cat_lotacao_e_outros_embarque', 'Densidade de carga e ocorrências complementares', TRUE),
('b2000000-0000-4000-8000-000000000001', 'b1000000-0000-4000-8000-000000000001', 'DESEMBARQUE', 'cat_estrutura_equipamento', 'Integridade física de carroceria, rampa e porteiras', TRUE),
('b2000000-0000-4000-8000-000000000002', 'b1000000-0000-4000-8000-000000000001', 'DESEMBARQUE', 'cat_manejo_recepcao_planta', 'Falhas de manejo e condução na recepção frigorífica', TRUE)
ON CONFLICT (tipo_etapa, codigo) DO UPDATE SET
    descricao       = EXCLUDED.descricao,
    anomalia_pai_id = EXCLUDED.anomalia_pai_id;

-- Nível 3: Vinculação das 15 anomalias folhas existentes às respectivas categorias
UPDATE sc_operacao.tb_dominio_anomalia
   SET anomalia_pai_id = 'a2000000-0000-4000-8000-000000000001'
 WHERE tipo_etapa = 'EMBARQUE'
   AND codigo IN ('sangrando', 'excesso_magreza_debilitado', 'mancando', 'sujo_pisoteio');

UPDATE sc_operacao.tb_dominio_anomalia
   SET anomalia_pai_id = 'a2000000-0000-4000-8000-000000000002'
 WHERE tipo_etapa = 'EMBARQUE'
   AND codigo IN ('cutucoes_fortes', 'tentativa_quebrar_cauda', 'chute_paulada_ferrao', 'arraste');

UPDATE sc_operacao.tb_dominio_anomalia
   SET anomalia_pai_id = 'a2000000-0000-4000-8000-000000000003'
 WHERE tipo_etapa = 'EMBARQUE'
   AND codigo IN ('gaiola_cheia', 'outro');

UPDATE sc_operacao.tb_dominio_anomalia
   SET anomalia_pai_id = 'b2000000-0000-4000-8000-000000000001'
 WHERE tipo_etapa = 'DESEMBARQUE'
   AND codigo IN ('gaiola_buraco_estrado_solto', 'porteiras_nao_abrem', 'problema_mecanico_veiculo');

UPDATE sc_operacao.tb_dominio_anomalia
   SET anomalia_pai_id = 'b2000000-0000-4000-8000-000000000002'
 WHERE tipo_etapa = 'DESEMBARQUE'
   AND codigo IN ('uso_abusivo_choque', 'outros_atos_abuso');


-- ==============================================================================
-- 4. REGISTROS INICIAIS DE AUDITORIA DE BACKUP E ATUALIZAÇÃO DE VIEW MATERIALIZADA
-- ==============================================================================
INSERT INTO sc_auditoria.tb_historico_backup (
    id, operacao, status, nome_banco, arquivo_dump, tamanho_bytes, checksum_sha256, iniciado_em, finalizado_em
) VALUES
(
    'f1000000-0000-4000-8000-000000000001',
    'BACKUP',
    'SUCESSO',
    current_database(),
    'efficientia_full_20261028_020000.dump',
    18452992,
    '3a7bd3e2360a3d29eea436fcfb7e44c735d117c42d1c1835420b6b9942dd4f1b',
    CURRENT_TIMESTAMP - INTERVAL '26 hours',
    CURRENT_TIMESTAMP - INTERVAL '25 hours 58 minutes'
),
(
    'f1000000-0000-4000-8000-000000000002',
    'BACKUP',
    'SUCESSO',
    current_database(),
    'efficientia_full_20261029_020000.dump',
    18974208,
    '8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4',
    CURRENT_TIMESTAMP - INTERVAL '2 hours',
    CURRENT_TIMESTAMP - INTERVAL '1 hour 58 minutes'
)
ON CONFLICT (id) DO NOTHING;

-- Sincroniza o catálogo para garantir 100% de cobertura após carga
CALL sc_auditoria.sp_sincronizar_catalogo_dados(FALSE);

-- Atualiza a view materializada do Data Mart após toda a carga histórica
REFRESH MATERIALIZED VIEW sc_operacao.mv_analise_mortalidade_mensal;

COMMIT;
