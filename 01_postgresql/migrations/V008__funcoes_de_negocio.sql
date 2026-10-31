-- ==============================================================================
-- EFFICIENTIA - MIGRATION V008: FUNCOES DE NEGOCIO E AUXILIARES
-- ==============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION sc_auditoria.fn_registrar_auditoria()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_empresa_id  UUID;
    v_dados_row   JSONB;
    v_dados_old   JSONB;
    v_dados_new   JSONB;
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_dados_old := row_to_json(OLD)::JSONB - 'senha_hash';
        v_dados_row := v_dados_old;
    ELSIF TG_OP = 'INSERT' THEN
        v_dados_new := row_to_json(NEW)::JSONB - 'senha_hash';
        v_dados_row := v_dados_new;
    ELSE -- UPDATE
        v_dados_old := row_to_json(OLD)::JSONB - 'senha_hash';
        v_dados_new := row_to_json(NEW)::JSONB - 'senha_hash';
        v_dados_row := v_dados_new;
    END IF;

    BEGIN
        v_empresa_id := (v_dados_row->>'empresa_id')::UUID;
    EXCEPTION WHEN OTHERS THEN
        v_empresa_id := NULL;
    END;

    INSERT INTO sc_auditoria.tb_auditoria_log (
        empresa_id,
        tabela_afetada,
        operacao,
        usuario_db,
        dados_antigos,
        dados_novos
    ) VALUES (
        v_empresa_id,
        TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
        TG_OP,
        SESSION_USER,
        v_dados_old,
        v_dados_new
    );

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

COMMIT;

BEGIN;

CREATE
OR REPLACE FUNCTION sc_auditoria.fn_registrar_acesso_diario(
    p_usuario_id UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
INSERT INTO sc_auditoria.tb_monitoramento_dau (usuario_id,
                                               data_acesso)

VALUES (p_usuario_id,
        CURRENT_DATE) ON CONFLICT (usuario_id, data_acesso) DO NOTHING;
END;
$$;

COMMIT;

BEGIN;

CREATE OR REPLACE FUNCTION sc_operacao.fn_validar_alocacao_viagem()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_data_vencimento_cnh     DATE;
    v_categoria_cnh           VARCHAR(5);
    v_data_vencimento_cavalo  DATE;
    v_data_vencimento_carreta DATE;
BEGIN
    SELECT data_vencimento_cnh, categoria_cnh
      INTO v_data_vencimento_cnh, v_categoria_cnh
      FROM sc_corporativo.tb_usuario
     WHERE id = NEW.motorista_id;

    IF v_data_vencimento_cnh IS NOT NULL AND v_data_vencimento_cnh < CURRENT_DATE THEN
        RAISE EXCEPTION 'Operação Bloqueada: Motorista selecionado possui CNH vencida em %.', v_data_vencimento_cnh
        USING ERRCODE = 'P0001';
    END IF;

    IF NEW.carreta_id IS NOT NULL AND LOWER(v_categoria_cnh) != 'e' THEN
        RAISE EXCEPTION 'Operação Bloqueada: Condução de combinação com carreta exige CNH categoria E (motorista possui %).', v_categoria_cnh
        USING ERRCODE = 'P0004';
    END IF;

    SELECT data_vencimento_inspecao
      INTO v_data_vencimento_cavalo
      FROM sc_frota.tb_veiculo_cavalo
     WHERE id = NEW.cavalo_id;

    IF v_data_vencimento_cavalo < CURRENT_DATE THEN
        RAISE EXCEPTION 'Operação Bloqueada: Cavalo selecionado está com a inspeção vencida desde %.', v_data_vencimento_cavalo
        USING ERRCODE = 'P0002';
    END IF;

    SELECT data_vencimento_inspecao
      INTO v_data_vencimento_carreta
      FROM sc_frota.tb_veiculo_carreta
     WHERE id = NEW.carreta_id;

    IF v_data_vencimento_carreta < CURRENT_DATE THEN
        RAISE EXCEPTION 'Operação Bloqueada: Carreta selecionada está com a inspeção vencida desde %.', v_data_vencimento_carreta
        USING ERRCODE = 'P0003';
    END IF;

    RETURN NEW;
END;
$$;

COMMIT;

BEGIN;

CREATE OR REPLACE FUNCTION sc_operacao.fn_gerar_outbox_relatorio()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_tipo_evento VARCHAR(100);
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_tipo_evento := 'relatorio.criado';
    ELSIF TG_OP = 'UPDATE' THEN
        IF OLD.status IS DISTINCT FROM NEW.status THEN
            v_tipo_evento := 'relatorio.status_alterado';
        ELSE
            RETURN NEW;
        END IF;
    END IF;

    INSERT INTO sc_operacao.tb_outbox_evento (
        empresa_id,
        tipo_evento,
        agregado_tipo,
        agregado_id,
        payload
    ) VALUES (
        NEW.empresa_id,
        v_tipo_evento,
        'relatorio_viagem',
        NEW.id,
        json_build_object(
            'relatorio_id', NEW.id,
            'empresa_id', NEW.empresa_id,
            'status_anterior', CASE WHEN TG_OP = 'UPDATE' THEN OLD.status ELSE NULL END,
            'status_novo', NEW.status,
            'motorista_id', NEW.motorista_id,
            'fazenda_id', NEW.fazenda_id,
            'cavalo_id', NEW.cavalo_id,
            'carreta_id', NEW.carreta_id,
            'qtd_machos', NEW.qtd_machos,
            'qtd_femeas', NEW.qtd_femeas,
            'qtd_marrucos', NEW.qtd_marrucos,
            'total_embarcados', (NEW.qtd_machos + NEW.qtd_femeas + NEW.qtd_marrucos),
            'qtd_em_pe', NEW.qtd_em_pe,
            'qtd_deitado', NEW.qtd_deitado,
            'qtd_morto', NEW.qtd_morto,
            'qtd_emergencia', NEW.qtd_emergencia,
            'data_chegada_unidade', NEW.data_chegada_unidade,
            'horario_chegada_unidade', NEW.horario_chegada_unidade,
            'horario_desembarque', NEW.horario_desembarque,
            'atualizado_em', CURRENT_TIMESTAMP
        )::jsonb
    );

    RETURN NEW;
END;
$$;

COMMIT;


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

