-- ==============================================================================
-- PROJETO EFFICIENTIA - SCRIPT DE DEMONSTRAÇÃO EXPLAIN ANALYZE
-- ==============================================================================
-- Executa medições reprodutíveis dos planos de execução das consultas críticas
-- de operação, multi-tenant e mensageria assíncrona.
-- ==============================================================================

BEGIN;

-- Ajusta formatação de saída para exibição detalhada de tempos e buffers
SET client_min_messages = notice;

-- ==============================================================================
-- 1. CONSULTA DE VIAGENS POR EMPRESA E ORDENAÇÃO TEMPORAL
-- ==============================================================================
RAISE NOTICE '--- EXPLAIN ANALYZE: Consulta de Viagens por Empresa e Data ---';

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT id, numero_gta, data_embarque, status, capacidade_carga_utilizada
FROM sc_operacao.tb_relatorio_viagem
WHERE empresa_id = 'c6aa229c-2c1d-56de-a6ea-280b898b0a7e'
ORDER BY data_embarque DESC
LIMIT 50;


-- ==============================================================================
-- 2. CONSULTA ANALÍTICA COM FILTRO DE STATUS (ÍNDICE PARCIAL)
-- ==============================================================================
RAISE NOTICE '--- EXPLAIN ANALYZE: Consulta Analítica de Viagens Aprovadas/Pendentes ---';

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT r.id, r.status, r.capacidade_carga_utilizada,
       (r.qtd_machos + r.qtd_femeas + r.qtd_marrucos) AS total_animais
FROM sc_operacao.tb_relatorio_viagem r
WHERE r.status IN ('pendente', 'aprovado');


-- ==============================================================================
-- 3. FILA DE EVENTOS PENDENTES DO OUTBOX (MENSAGERIA ASSÍNCRONA)
-- ==============================================================================
RAISE NOTICE '--- EXPLAIN ANALYZE: Fila de Publicação do Transactional Outbox ---';

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT id, tipo_evento, payload, criado_em
FROM sc_operacao.tb_outbox_evento
WHERE processado_em IS NULL
ORDER BY criado_em ASC
LIMIT 100;


-- ==============================================================================
-- 4. DEMONSTRAÇÃO DE ÍNDICE DESCARTADO POR BAIXA SELETIVIDADE
-- ==============================================================================
RAISE NOTICE '--- EXPLAIN ANALYZE: Demonstração de Varredura em Coluna Booleana ---';

EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
SELECT id, status, sirene_re_funcionou
FROM sc_operacao.tb_relatorio_viagem
WHERE sirene_re_funcionou = TRUE;

ROLLBACK;
