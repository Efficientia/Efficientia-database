BEGIN;

-- ==============================================================================
-- 1. FUNÇÃO DE PREVENÇÃO DE CICLOS E CONSISTÊNCIA DE ETAPA EM HIERARQUIA (TRIGGER)
-- ==============================================================================
CREATE OR REPLACE FUNCTION sc_operacao.fn_verificar_ciclo_anomalia()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_etapa_pai      VARCHAR(20);
    v_ciclo_detectado BOOLEAN;
BEGIN
    IF NEW.anomalia_pai_id IS NULL THEN
        RETURN NEW;
    END IF;

    IF NEW.anomalia_pai_id = NEW.id THEN
        RAISE EXCEPTION 'Uma anomalia não pode referenciar a si mesma como anomalia pai.'
            USING ERRCODE = 'P0008';
    END IF;

    SELECT d.tipo_etapa
      INTO v_etapa_pai
      FROM sc_operacao.tb_dominio_anomalia d
     WHERE d.id = NEW.anomalia_pai_id;

    IF v_etapa_pai IS NULL THEN
        RAISE EXCEPTION 'Anomalia pai informada (%) não existe no catálogo.', NEW.anomalia_pai_id
            USING ERRCODE = 'P0008';
    END IF;

    IF v_etapa_pai <> NEW.tipo_etapa THEN
        RAISE EXCEPTION 'Incompatibilidade de etapa na hierarquia: o nó pai pertence a % e o nó filho a %.',
            v_etapa_pai, NEW.tipo_etapa
            USING ERRCODE = 'P0009';
    END IF;

    -- Percorre os ancestrais a partir do candidato a pai usando UNION para encerrar em grafos cíclicos
    WITH RECURSIVE cte_ancestrais AS (
        SELECT d.id, d.anomalia_pai_id
          FROM sc_operacao.tb_dominio_anomalia d
         WHERE d.id = NEW.anomalia_pai_id

        UNION

        SELECT p.id, p.anomalia_pai_id
          FROM sc_operacao.tb_dominio_anomalia p
         INNER JOIN cte_ancestrais a ON p.id = a.anomalia_pai_id
    )
    SELECT EXISTS (
        SELECT 1
          FROM cte_ancestrais
         WHERE id = NEW.id
    )
      INTO v_ciclo_detectado;

    IF v_ciclo_detectado THEN
        RAISE EXCEPTION 'Ciclo hierárquico detectado no catálogo de anomalias ao vincular % como filho de %.',
            NEW.id, NEW.anomalia_pai_id
            USING ERRCODE = 'P0008';
    END IF;

    RETURN NEW;
END;
$$;


-- ==============================================================================
-- 2. FUNÇÃO TABULAR RECURSIVA PARA EXTRAÇÃO DE SUBÁRVORE DE ANOMALIA
-- ==============================================================================
CREATE OR REPLACE FUNCTION sc_operacao.fn_obter_subarvore_anomalia(p_anomalia_id UUID)
RETURNS TABLE (
    id                 UUID,
    anomalia_pai_id    UUID,
    tipo_etapa         VARCHAR(20),
    codigo             VARCHAR(50),
    descricao          VARCHAR(150),
    nivel_relativo     INTEGER,
    caminho_relativo   TEXT
)
LANGUAGE sql
STABLE
SET search_path = pg_catalog, pg_temp
AS $$
    WITH RECURSIVE cte_subarvore AS (
        SELECT
            d.id,
            d.anomalia_pai_id,
            d.tipo_etapa,
            d.codigo,
            d.descricao,
            0                 AS nivel_relativo,
            d.codigo::TEXT    AS caminho_relativo,
            ARRAY[d.id]       AS visitados
        FROM sc_operacao.tb_dominio_anomalia d
        WHERE d.id = p_anomalia_id

        UNION ALL

        SELECT
            f.id,
            f.anomalia_pai_id,
            f.tipo_etapa,
            f.codigo,
            f.descricao,
            s.nivel_relativo + 1,
            s.caminho_relativo || ' > ' || f.codigo,
            s.visitados || f.id
        FROM sc_operacao.tb_dominio_anomalia f
        INNER JOIN cte_subarvore s ON f.anomalia_pai_id = s.id
        WHERE NOT (f.id = ANY(s.visitados))
    )
    SELECT
        id,
        anomalia_pai_id,
        tipo_etapa,
        codigo,
        descricao,
        nivel_relativo,
        caminho_relativo
    FROM cte_subarvore
    ORDER BY nivel_relativo, codigo;
$$;


-- ==============================================================================
-- 3. FUNÇÃO DE AUDITORIA VOLUMÉTRICA PÓS-RESTAURAÇÃO DE BACKUP
-- ==============================================================================
CREATE OR REPLACE FUNCTION sc_auditoria.fn_contagem_linhas_tabelas()
RETURNS TABLE (
    esquema_nome TEXT,
    tabela_nome  TEXT,
    total_linhas BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    r_tab RECORD;
    v_qtd BIGINT;
BEGIN
    FOR r_tab IN
        SELECT n.nspname::TEXT AS esquema, c.relname::TEXT AS tabela
          FROM pg_catalog.pg_class c
         INNER JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname IN ('sc_auditoria', 'sc_corporativo', 'sc_frota', 'sc_operacao')
           AND c.relkind = 'r'
         ORDER BY n.nspname, c.relname
    LOOP
        EXECUTE format('SELECT COUNT(*) FROM %I.%I', r_tab.esquema, r_tab.tabela)
           INTO v_qtd;

        esquema_nome := r_tab.esquema;
        tabela_nome  := r_tab.tabela;
        total_linhas := v_qtd;
        RETURN NEXT;
    END LOOP;
END;
$$;

COMMIT;
