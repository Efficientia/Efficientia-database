BEGIN;

-- ==============================================================================
-- 1. CAMADA DIMENSIONAL
-- ==============================================================================

-- Dimensão de Empresas
CREATE
OR REPLACE VIEW sc_corporativo.vw_dim_empresa AS
SELECT id   AS sk_empresa,
       nome AS nome_empresa,
       cnpj AS cnpj_empresa,
       codigo_interno
FROM sc_corporativo.tb_empresa;

-- Dimensão de Colaboradores (Motoristas, Analistas, etc.)
CREATE
OR REPLACE VIEW sc_corporativo.vw_dim_colaborador AS
SELECT id            AS sk_colaborador,
       empresa_id    AS fk_empresa,
       nome_completo AS nome,
       tipo          AS tipo_perfil,
       cargo,
       categoria_cnh,
       status_cadastro
FROM sc_corporativo.tb_usuario;

-- Dimensão de Frota (Unificando Cavalo e Carreta)
CREATE
OR REPLACE VIEW sc_frota.vw_dim_frota AS
SELECT id         AS sk_veiculo,
       empresa_id AS fk_empresa,
       placa,
       ativo      AS status_ativo,
       CASE
           WHEN tableoid = 'sc_frota.tb_veiculo_cavalo'::regclass THEN 'Cavalo'
           WHEN tableoid = 'sc_frota.tb_veiculo_carreta'::regclass THEN 'Carreta'
           ELSE 'Base'
           END    AS tipo_veiculo
FROM sc_frota.tb_veiculo_base;

-- Dimensão Unificada de Localidades (Origens e Destinos)
CREATE
OR REPLACE VIEW sc_corporativo.vw_dim_localidade AS
SELECT id         AS sk_localidade,
       empresa_id AS fk_empresa,
       nome       AS nome_local,
       'FAZENDA'  AS tipo_localidade,
       cnpj       AS documento
FROM sc_corporativo.tb_fazenda
UNION ALL
SELECT id            AS sk_localidade,
       empresa_id    AS fk_empresa,
       nome          AS nome_local,
       'FRIGORÍFICO' AS tipo_localidade,
       cnpj          AS documento
FROM sc_corporativo.tb_unidade_frigorifica;

-- ==============================================================================
-- 2. CAMADA FATO (TRANSFORMAÇÃO E ETL VIA CTE)
-- ==============================================================================

CREATE
OR REPLACE VIEW sc_operacao.vw_fato_transporte_animal AS
WITH cte_paradas_consolidadas AS (
    SELECT
        relatorio_id,
        COUNT(id) AS qtd_paradas,
        SUM(EXTRACT(EPOCH FROM (data_hora_fim - data_hora_inicio)) / 3600.0) AS tempo_parada_horas
    FROM sc_operacao.tb_parada_imprevista
    GROUP BY relatorio_id
),
cte_anomalias_consolidadas AS (
    SELECT
        relatorio_id,
        COUNT(id) AS qtd_anomalias
    FROM sc_operacao.tb_anomalia_embarque
    GROUP BY relatorio_id
    UNION ALL
    SELECT
        relatorio_id,
        COUNT(id) AS qtd_anomalias
    FROM sc_operacao.tb_anomalia_desembarque
    GROUP BY relatorio_id
),
cte_agrupamento_anomalias AS (
    SELECT relatorio_id, SUM(qtd_anomalias) AS total_anomalias
    FROM cte_anomalias_consolidadas
    GROUP BY relatorio_id
)
SELECT r.id                                                           AS sk_fato_viagem,
       r.empresa_id                                                   AS fk_empresa,
       r.fazenda_id                                                   AS fk_origem,
       r.motorista_id                                                 AS fk_motorista,
       r.cavalo_id                                                    AS fk_cavalo,
       r.carreta_id                                                   AS fk_carreta,

       r.data_chegada_unidade                                         AS data_referencia,
       r.status                                                       AS status_viagem,

       r.capacidade_carga_utilizada,

       -- 1. Métricas Brutas de Embarque
       r.qtd_machos,
       r.qtd_femeas,
       r.qtd_marrucos,
       (r.qtd_machos + r.qtd_femeas + r.qtd_marrucos)                 AS total_animais_embarcados,

       -- 2. Métricas Brutas de Desembarque
       r.qtd_em_pe,
       r.qtd_deitado,
       r.qtd_morto,
       r.qtd_emergencia,
       (r.qtd_em_pe + r.qtd_deitado + r.qtd_morto + r.qtd_emergencia) AS total_animais_desembarcados,

       -- 3. Métrica de Auditoria
       -- Resultado 0 = Carga Perfeita.
       -- Resultado Negativo = Faltou animal (Roubo/Fuga).
       -- Resultado Positivo = Sobrou animal (Erro de contagem na origem).
       (r.qtd_em_pe + r.qtd_deitado + r.qtd_morto + r.qtd_emergencia) -
       (r.qtd_machos + r.qtd_femeas + r.qtd_marrucos)                 AS quebra_inventario_cabecas,

       -- 4. Métricas Transformadas de Operação (ETL via CTE)
       COALESCE(p.qtd_paradas, 0)                                     AS qtd_paradas,
       COALESCE(p.tempo_parada_horas, 0.0)                            AS tempo_parada_horas,
       COALESCE(a.total_anomalias, 0)                                 AS qtd_anomalias,

       -- 5. Cálculos de Desempenho de Frota
       (r.km_chegada_desembarcadouro - r.km_saida_embarcadouro)       AS km_rodados

FROM sc_operacao.tb_relatorio_viagem r
         LEFT JOIN cte_paradas_consolidadas p ON r.id = p.relatorio_id
         LEFT JOIN cte_agrupamento_anomalias a ON r.id = a.relatorio_id
WHERE r.status IN ('pendente', 'aprovado');


-- ==============================================================================
-- 3. VIEWS MATERIALIZADAS (CÁLCULOS ANALÍTICOS AVANÇADOS / WINDOW FUNCTIONS)
-- ==============================================================================
CREATE
MATERIALIZED VIEW sc_operacao.mv_analise_mortalidade_mensal AS
SELECT fk_empresa,
    fk_origem,
    fk_motorista,
    DATE_TRUNC('month', data_referencia) AS mes_referencia,

    SUM(total_animais_embarcados)        AS volume_animais_mes,
    SUM(qtd_morto)                       AS total_mortes_mes,

    ROUND(
            (SUM(qtd_morto)::NUMERIC / NULLIF(SUM(total_animais_embarcados), 0)) * 100,
            2
    )                                    AS taxa_mortalidade_percentual,

    -- Window Function 1: Running Total (Soma Acumulada) de mortes da empresa no ano
    SUM(SUM(qtd_morto))                     OVER (
        PARTITION BY fk_empresa, EXTRACT(YEAR FROM data_referencia)
        ORDER BY DATE_TRUNC('month', data_referencia)
    ) AS acumulado_mortes_ano,

    -- Window Function 2: Ranking de motoristas com maior taxa de mortalidade na empresa
    RANK() OVER (
        PARTITION BY fk_empresa, DATE_TRUNC('month', data_referencia)
        ORDER BY SUM(qtd_morto) DESC
    ) AS rank_mortalidade_motorista

FROM sc_operacao.vw_fato_transporte_animal
WHERE status_viagem = 'aprovado'
GROUP BY fk_empresa,
         fk_origem,
         fk_motorista,
         DATE_TRUNC('month', data_referencia);

CREATE UNIQUE INDEX uidx_mv_analise_mortalidade
    ON sc_operacao.mv_analise_mortalidade_mensal (fk_empresa, fk_origem, fk_motorista, mes_referencia);

COMMIT;

-- ==============================================================================
-- INSTRUÇÃO DE MANUTENÇÃO
-- Executar periodicamente para atualizar os dados analíticos do painel sem bloquear o banco:
-- REFRESH MATERIALIZED VIEW CONCURRENTLY sc_operacao.mv_analise_mortalidade_mensal;
-- ==============================================================================