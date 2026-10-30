-- ==============================================================================
-- EFFICIENTIA - MIGRATION V007: VIEWS ANALITICAS, DATA MART E GOVERNANCA
-- ==============================================================================

BEGIN;

-- ==============================================================================
-- 1. CAMADA DIMENSIONAL
-- ==============================================================================

-- Dimensão de Empresas
CREATE OR REPLACE VIEW sc_corporativo.vw_dim_empresa AS
SELECT id   AS sk_empresa,
       nome AS nome_empresa,
       cnpj AS cnpj_empresa,
       codigo_interno
FROM sc_corporativo.tb_empresa;

-- Dimensão de Colaboradores (Motoristas, Analistas, etc.)
CREATE OR REPLACE VIEW sc_corporativo.vw_dim_colaborador AS
SELECT id            AS sk_colaborador,
       empresa_id    AS fk_empresa,
       nome_completo AS nome,
       tipo          AS tipo_perfil,
       cargo,
       categoria_cnh,
       status_cadastro
FROM sc_corporativo.tb_usuario;

-- Dimensão de Frota (Unificando Cavalo e Carreta)
CREATE OR REPLACE VIEW sc_frota.vw_dim_frota AS
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
CREATE OR REPLACE VIEW sc_corporativo.vw_dim_localidade AS
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

CREATE OR REPLACE VIEW sc_operacao.vw_fato_transporte_animal AS
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
CREATE MATERIALIZED VIEW IF NOT EXISTS sc_operacao.mv_analise_mortalidade_mensal AS
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
    SUM(SUM(qtd_morto)) OVER (
        PARTITION BY fk_empresa, EXTRACT(YEAR FROM DATE_TRUNC('month', data_referencia))
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

CREATE UNIQUE INDEX IF NOT EXISTS uidx_mv_analise_mortalidade
    ON sc_operacao.mv_analise_mortalidade_mensal (fk_empresa, fk_origem, fk_motorista, mes_referencia);

COMMIT;

-- ==============================================================================
-- INSTRUÇÃO DE MANUTENÇÃO
-- Executar periodicamente para atualizar os dados analíticos do painel sem bloquear o banco:
-- REFRESH MATERIALIZED VIEW CONCURRENTLY sc_operacao.mv_analise_mortalidade_mensal;
-- ==============================================================================


BEGIN;

-- ==============================================================================
-- 1. ÁRVORE HIERÁRQUICA DE ANOMALIAS (CTE RECURSIVA - WITH RECURSIVE)
-- ==============================================================================
CREATE OR REPLACE VIEW sc_operacao.vw_arvore_dominio_anomalia AS
WITH RECURSIVE cte_arvore_anomalia AS (
    -- Caso base: nós raiz (sem anomalia pai)
    SELECT
        d.id,
        d.anomalia_pai_id,
        d.tipo_etapa,
        d.codigo,
        d.descricao,
        d.ativo,
        1                        AS nivel_hierarquia,
        d.codigo::TEXT           AS caminho_codigos,
        d.descricao::TEXT        AS caminho_completo,
        ARRAY[d.id]              AS caminho_ids,
        d.id                     AS raiz_id,
        d.codigo                 AS raiz_codigo
    FROM sc_operacao.tb_dominio_anomalia d
    WHERE d.anomalia_pai_id IS NULL

    UNION ALL

    -- Passo recursivo: expansão dos nós filhos com guarda contra ciclos
    SELECT
        f.id,
        f.anomalia_pai_id,
        f.tipo_etapa,
        f.codigo,
        f.descricao,
        f.ativo,
        a.nivel_hierarquia + 1                       AS nivel_hierarquia,
        a.caminho_codigos || ' > ' || f.codigo       AS caminho_codigos,
        a.caminho_completo || ' > ' || f.descricao   AS caminho_completo,
        a.caminho_ids || f.id                        AS caminho_ids,
        a.raiz_id,
        a.raiz_codigo
    FROM sc_operacao.tb_dominio_anomalia f
    INNER JOIN cte_arvore_anomalia a ON f.anomalia_pai_id = a.id
    WHERE NOT (f.id = ANY(a.caminho_ids))
)
SELECT
    c.id,
    c.anomalia_pai_id,
    c.tipo_etapa,
    c.codigo,
    c.descricao,
    c.ativo,
    c.nivel_hierarquia,
    c.caminho_codigos,
    c.caminho_completo,
    c.caminho_ids,
    c.raiz_id,
    c.raiz_codigo,
    NOT EXISTS (
        SELECT 1
        FROM sc_operacao.tb_dominio_anomalia sub
        WHERE sub.anomalia_pai_id = c.id
    ) AS eh_folha
FROM cte_arvore_anomalia c;


-- ==============================================================================
-- 2. AGREGAÇÃO HIERÁRQUICA DE OCORRÊNCIAS POR SUBÁRVORE (CTE RECURSIVA + WINDOW)
-- ==============================================================================
CREATE OR REPLACE VIEW sc_operacao.vw_ocorrencias_por_arvore_anomalia AS
WITH RECURSIVE cte_subarvore AS (
    SELECT
        id AS ancestral_id,
        id AS descendente_id,
        ARRAY[id] AS trilha
    FROM sc_operacao.tb_dominio_anomalia

    UNION ALL

    SELECT
        s.ancestral_id,
        f.id AS descendente_id,
        s.trilha || f.id
    FROM cte_subarvore s
    INNER JOIN sc_operacao.tb_dominio_anomalia f ON f.anomalia_pai_id = s.descendente_id
    WHERE NOT (f.id = ANY(s.trilha))
),
cte_apontamentos_brutos AS (
    SELECT dominio_anomalia_id, COUNT(id) AS qtd
    FROM sc_operacao.tb_anomalia_embarque
    GROUP BY dominio_anomalia_id

    UNION ALL

    SELECT dominio_anomalia_id, COUNT(id) AS qtd
    FROM sc_operacao.tb_anomalia_desembarque
    GROUP BY dominio_anomalia_id
),
cte_ocorrencias_diretas AS (
    SELECT dominio_anomalia_id, SUM(qtd) AS total_direto
    FROM cte_apontamentos_brutos
    GROUP BY dominio_anomalia_id
),
cte_rollup_subarvore AS (
    SELECT
        s.ancestral_id AS anomalia_id,
        COALESCE(SUM(od.total_direto), 0) AS ocorrencias_acumuladas_subarvore
    FROM cte_subarvore s
    LEFT JOIN cte_ocorrencias_diretas od ON od.dominio_anomalia_id = s.descendente_id
    GROUP BY s.ancestral_id
)
SELECT
    arv.id AS anomalia_id,
    arv.anomalia_pai_id,
    arv.tipo_etapa,
    arv.nivel_hierarquia,
    arv.codigo,
    arv.descricao,
    arv.caminho_codigos,
    arv.eh_folha,
    COALESCE(od.total_direto, 0)         AS ocorrencias_diretas,
    rol.ocorrencias_acumuladas_subarvore AS ocorrencias_subarvore,
    RANK() OVER (
        PARTITION BY arv.tipo_etapa, arv.nivel_hierarquia
        ORDER BY rol.ocorrencias_acumuladas_subarvore DESC
    )                                    AS ranking_no_nivel,
    ROUND(
        (rol.ocorrencias_acumuladas_subarvore::NUMERIC /
         NULLIF(SUM(COALESCE(od.total_direto, 0)) OVER (PARTITION BY arv.tipo_etapa), 0)) * 100,
        2
    )                                    AS participacao_etapa_perc
FROM sc_operacao.vw_arvore_dominio_anomalia arv
INNER JOIN cte_rollup_subarvore rol ON rol.anomalia_id = arv.id
LEFT JOIN cte_ocorrencias_diretas od ON od.dominio_anomalia_id = arv.id;


-- ==============================================================================
-- 3. CATÁLOGO DE DADOS ATIVO CRUZADO COM PG_CATALOG E LGPD
-- ==============================================================================
CREATE OR REPLACE VIEW sc_auditoria.vw_catalogo_dados_completo AS
WITH cte_colunas_fisicas AS (
    SELECT
        n.nspname                                            AS esquema_nome,
        c.relname                                            AS tabela_nome,
        a.attname                                            AS coluna_nome,
        a.attnum                                             AS ordem_coluna,
        pg_catalog.format_type(a.atttypid, a.atttypmod)      AS tipo_dado_fisico,
        a.attnotnull                                         AS obrigatorio,
        (a.attinhcount > 0)                                  AS coluna_herdada,
        np.nspname                                           AS esquema_pai_heranca,
        cp.relname                                           AS tabela_pai_heranca,
        EXISTS (
            SELECT 1
            FROM pg_catalog.pg_constraint con
            WHERE con.conrelid = c.oid
              AND con.contype = 'p'
              AND a.attnum = ANY(con.conkey)
        )                                                    AS eh_chave_primaria,
        EXISTS (
            SELECT 1
            FROM pg_catalog.pg_constraint con
            WHERE con.conrelid = c.oid
              AND con.contype = 'f'
              AND a.attnum = ANY(con.conkey)
        )                                                    AS eh_chave_estrangeira
    FROM pg_catalog.pg_class c
    INNER JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    INNER JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
    LEFT JOIN pg_catalog.pg_inherits inh ON inh.inhrelid = c.oid AND inh.inhseqno = 1
    LEFT JOIN pg_catalog.pg_class cp ON cp.oid = inh.inhparent
    LEFT JOIN pg_catalog.pg_namespace np ON np.oid = cp.relnamespace
    WHERE n.nspname IN ('sc_auditoria', 'sc_corporativo', 'sc_frota', 'sc_operacao')
      AND c.relkind = 'r'
      AND a.attnum > 0
      AND NOT a.attisdropped
)
SELECT
    f.esquema_nome,
    f.tabela_nome,
    f.coluna_nome,
    f.ordem_coluna,
    f.tipo_dado_fisico,
    f.obrigatorio,
    f.eh_chave_primaria,
    f.eh_chave_estrangeira,
    f.coluna_herdada,
    f.tabela_pai_heranca,
    COALESCE(cd.descricao, cp_cat.descricao)                         AS descricao,
    COALESCE(cd.regra_negocio_critica, cp_cat.regra_negocio_critica) AS regra_negocio_critica,
    COALESCE(cd.nivel_acesso_leitura, cp_cat.nivel_acesso_leitura)   AS nivel_acesso_leitura,
    COALESCE(cd.nivel_acesso_escrita, cp_cat.nivel_acesso_escrita)   AS nivel_acesso_escrita,
    COALESCE(cd.dado_pessoal_lgpd, cp_cat.dado_pessoal_lgpd, FALSE)  AS dado_pessoal_lgpd,
    (COALESCE(cd.id, cp_cat.id) IS NOT NULL)                         AS esta_documentado,
    TRUE                                                             AS existe_no_schema,
    COALESCE(cd.atualizado_em, cp_cat.atualizado_em)                 AS atualizado_em
FROM cte_colunas_fisicas f
LEFT JOIN sc_auditoria.tb_catalogo_dados cd
    ON cd.esquema_nome = f.esquema_nome
   AND cd.tabela_nome = f.tabela_nome
   AND cd.coluna_nome = f.coluna_nome
LEFT JOIN sc_auditoria.tb_catalogo_dados cp_cat
    ON f.coluna_herdada = TRUE
   AND cp_cat.esquema_nome = f.esquema_pai_heranca
   AND cp_cat.tabela_nome = f.tabela_pai_heranca
   AND cp_cat.coluna_nome = f.coluna_nome

UNION ALL

-- Colunas órfãs presentes no catálogo, mas removidas do schema físico
SELECT
    cat.esquema_nome,
    cat.tabela_nome,
    cat.coluna_nome,
    NULL::SMALLINT          AS ordem_coluna,
    NULL::TEXT              AS tipo_dado_fisico,
    NULL::BOOLEAN           AS obrigatorio,
    FALSE                   AS eh_chave_primaria,
    FALSE                   AS eh_chave_estrangeira,
    FALSE                   AS coluna_herdada,
    NULL::NAME              AS tabela_pai_heranca,
    cat.descricao,
    cat.regra_negocio_critica,
    cat.nivel_acesso_leitura,
    cat.nivel_acesso_escrita,
    cat.dado_pessoal_lgpd,
    TRUE                    AS esta_documentado,
    FALSE                   AS existe_no_schema,
    cat.atualizado_em
FROM sc_auditoria.tb_catalogo_dados cat
WHERE NOT EXISTS (
    SELECT 1
    FROM cte_colunas_fisicas f2
    WHERE f2.esquema_nome = cat.esquema_nome
      AND f2.tabela_nome = cat.tabela_nome
      AND f2.coluna_nome = cat.coluna_nome
);


CREATE OR REPLACE VIEW sc_auditoria.vw_resumo_catalogo_tabelas AS
SELECT
    v.esquema_nome,
    v.tabela_nome,
    MAX(v.tabela_pai_heranca::TEXT)                                AS tabela_pai_heranca,
    COUNT(*)                                                       AS total_colunas,
    COUNT(*) FILTER (WHERE v.esta_documentado)                     AS colunas_documentadas,
    ROUND(
        (COUNT(*) FILTER (WHERE v.esta_documentado)::NUMERIC / NULLIF(COUNT(*), 0)) * 100,
        2
    )                                                              AS cobertura_documentacao_perc,
    COUNT(*) FILTER (WHERE v.dado_pessoal_lgpd)                    AS qtd_colunas_lgpd,
    BOOL_OR(v.dado_pessoal_lgpd)                                   AS contem_dados_pessoais,
    GREATEST(COALESCE(c.reltuples::BIGINT, 0), 0)                  AS linhas_estimadas
FROM sc_auditoria.vw_catalogo_dados_completo v
INNER JOIN pg_catalog.pg_namespace n ON n.nspname = v.esquema_nome
INNER JOIN pg_catalog.pg_class c ON c.relnamespace = n.oid AND c.relname = v.tabela_nome
WHERE v.existe_no_schema = TRUE
GROUP BY v.esquema_nome, v.tabela_nome, c.reltuples;


-- ==============================================================================
-- 4. MONITORAMENTO ANALÍTICO DE ENGAJAMENTO (DAU / MAU / STICKINESS)
-- ==============================================================================
CREATE OR REPLACE VIEW sc_auditoria.vw_metricas_dau_mau AS
WITH cte_limites AS (
    SELECT
        MIN(data_acesso) AS dt_inicio,
        MAX(data_acesso) AS dt_fim
    FROM sc_auditoria.tb_monitoramento_dau
),
cte_calendario AS (
    SELECT gs::DATE AS data_referencia
    FROM cte_limites l
    CROSS JOIN LATERAL generate_series(l.dt_inicio, l.dt_fim, INTERVAL '1 day') AS gs
    WHERE l.dt_inicio IS NOT NULL
),
cte_dau_diario AS (
    SELECT
        c.data_referencia,
        COUNT(DISTINCT d.usuario_id) AS dau
    FROM cte_calendario c
    LEFT JOIN sc_auditoria.tb_monitoramento_dau d
        ON d.data_acesso = c.data_referencia
    GROUP BY c.data_referencia
),
cte_mau_movel AS (
    SELECT
        c.data_referencia,
        (
            SELECT COUNT(DISTINCT m.usuario_id)
            FROM sc_auditoria.tb_monitoramento_dau m
            WHERE m.data_acesso BETWEEN (c.data_referencia - INTERVAL '29 days')::DATE AND c.data_referencia
        ) AS mau_30d
    FROM cte_calendario c
)
SELECT
    d.data_referencia,
    d.dau,
    LAG(d.dau) OVER (ORDER BY d.data_referencia)                     AS dau_dia_anterior,
    d.dau - LAG(d.dau) OVER (ORDER BY d.data_referencia)             AS variacao_diaria_abs,
    ROUND(
        AVG(d.dau) OVER (
            ORDER BY d.data_referencia
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ),
        2
    )                                                                AS media_movel_7d,
    m.mau_30d,
    ROUND(
        (d.dau::NUMERIC / NULLIF(m.mau_30d, 0)) * 100,
        2
    )                                                                AS stickiness_perc
FROM cte_dau_diario d
INNER JOIN cte_mau_movel m ON m.data_referencia = d.data_referencia;


CREATE OR REPLACE VIEW sc_auditoria.vw_dau_por_empresa AS
WITH cte_base_usuarios AS (
    SELECT
        empresa_id,
        COUNT(*) FILTER (WHERE status_cadastro = 'ativo') AS usuarios_ativos_empresa
    FROM sc_corporativo.tb_usuario
    GROUP BY empresa_id
)
SELECT
    d.data_acesso                                                    AS data_referencia,
    e.id                                                             AS empresa_id,
    e.nome                                                           AS nome_empresa,
    COUNT(DISTINCT d.usuario_id)                                     AS dau_empresa,
    COALESCE(bu.usuarios_ativos_empresa, 0)                          AS usuarios_ativos_empresa,
    ROUND(
        (COUNT(DISTINCT d.usuario_id)::NUMERIC / NULLIF(bu.usuarios_ativos_empresa, 0)) * 100,
        2
    )                                                                AS taxa_adocao_diaria_perc,
    RANK() OVER (
        PARTITION BY d.data_acesso
        ORDER BY COUNT(DISTINCT d.usuario_id) DESC
    )                                                                AS ranking_engajamento_dia
FROM sc_auditoria.tb_monitoramento_dau d
INNER JOIN sc_corporativo.tb_usuario u ON u.id = d.usuario_id
INNER JOIN sc_corporativo.tb_empresa e ON e.id = u.empresa_id
LEFT JOIN cte_base_usuarios bu ON bu.empresa_id = e.id
GROUP BY d.data_acesso, e.id, e.nome, bu.usuarios_ativos_empresa;


-- ==============================================================================
-- 5. PAINEL DE GOVERNANÇA DE BACKUPS E RPO
-- ==============================================================================
CREATE OR REPLACE VIEW sc_auditoria.vw_status_backups AS
SELECT
    b.id,
    b.operacao,
    b.status,
    b.nome_banco,
    b.arquivo_dump,
    ROUND(COALESCE(b.tamanho_bytes, 0)::NUMERIC / (1024.0 * 1024.0), 2) AS tamanho_mb,
    b.checksum_sha256,
    b.iniciado_em,
    b.finalizado_em,
    ROUND(
        EXTRACT(EPOCH FROM (COALESCE(b.finalizado_em, CURRENT_TIMESTAMP) - b.iniciado_em))::NUMERIC,
        2
    )                                                                   AS duracao_segundos,
    ROUND(
        (EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - COALESCE(b.finalizado_em, b.iniciado_em))) / 3600.0)::NUMERIC,
        2
    )                                                                   AS horas_desde_execucao,
    (
        b.status = 'SUCESSO'
        AND EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - COALESCE(b.finalizado_em, b.iniciado_em))) / 3600.0 <= 24.0
    )                                                                   AS dentro_janela_rpo_24h,
    b.executado_por,
    b.mensagem_erro
FROM sc_auditoria.tb_historico_backup b;

COMMIT;

