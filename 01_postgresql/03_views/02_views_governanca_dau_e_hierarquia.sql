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
