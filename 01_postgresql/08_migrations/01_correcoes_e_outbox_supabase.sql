BEGIN;

-- ==============================================================================
-- 1. CORREÇÃO DE ÍNDICES (REMOVER DUPLICADOS E ADICIONAR EM TABELAS FILHAS)
-- ==============================================================================
-- Remove índices redundantes que já são cobertos por constraints UNIQUE
DROP INDEX IF EXISTS sc_corporativo.idx_usuario_cpf;
DROP INDEX IF EXISTS sc_frota.idx_veiculo_base_placa;
DROP INDEX IF EXISTS sc_operacao.idx_relatorio_gta;

-- Adiciona índices de isolamento multi-tenant nas tabelas filhas (INHERITS)
CREATE INDEX IF NOT EXISTS idx_veiculo_cavalo_empresa ON sc_frota.tb_veiculo_cavalo (empresa_id);
CREATE INDEX IF NOT EXISTS idx_veiculo_carreta_empresa ON sc_frota.tb_veiculo_carreta (empresa_id);

-- ==============================================================================
-- 2. TABELA DE MENSAGERIA / TRANSACTIONAL OUTBOX (INTEGRAÇÃO COM REDIS)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS sc_operacao.tb_outbox_evento
(
    id              UUID         DEFAULT gen_random_uuid(),
    empresa_id      UUID         NOT NULL,
    tipo_evento     VARCHAR(100) NOT NULL,
    agregado_tipo   VARCHAR(50)  NOT NULL DEFAULT 'relatorio_viagem',
    agregado_id     UUID         NOT NULL,
    payload         JSONB        NOT NULL,
    criado_em       TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP,
    processado_em   TIMESTAMPTZ,
    erro_tentativas INTEGER      NOT NULL DEFAULT 0,
    ultimo_erro     TEXT,
    CONSTRAINT pk_outbox_evento PRIMARY KEY (id),
    CONSTRAINT fk_outbox_empresa FOREIGN KEY (empresa_id) REFERENCES sc_corporativo.tb_empresa (id) ON DELETE CASCADE
);

-- Índice parcial de alto desempenho: busca apenas eventos pendentes ordenados cronologicamente
CREATE INDEX IF NOT EXISTS idx_outbox_pendentes
    ON sc_operacao.tb_outbox_evento (criado_em) WHERE processado_em IS NULL;

-- ==============================================================================
-- 3. ATUALIZAÇÃO DA AUDITORIA (SEGURANÇA E CONFORMIDADE LGPD)
-- ==============================================================================
-- Adiciona search_path seguro e mascara a senha_hash
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

-- ==============================================================================
-- 4. FUNÇÃO E TRIGGER PARA DISPARO DA OUTBOX
-- ==============================================================================
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

DROP TRIGGER IF EXISTS tg_outbox_relatorio_viagem ON sc_operacao.tb_relatorio_viagem;
CREATE TRIGGER tg_outbox_relatorio_viagem
    AFTER INSERT OR UPDATE OF status ON sc_operacao.tb_relatorio_viagem
    FOR EACH ROW EXECUTE FUNCTION sc_operacao.fn_gerar_outbox_relatorio();

-- ==============================================================================
-- 5. CORREÇÃO DO TRIGGER DE ALOCAÇÃO DE FROTA
-- ==============================================================================
DROP TRIGGER IF EXISTS tg_validar_alocacao_viagem ON sc_operacao.tb_relatorio_viagem;
CREATE TRIGGER tg_validar_alocacao_viagem
    BEFORE INSERT OR UPDATE OF motorista_id, cavalo_id, carreta_id ON sc_operacao.tb_relatorio_viagem
    FOR EACH ROW EXECUTE FUNCTION sc_operacao.fn_validar_alocacao_viagem();

-- ==============================================================================
-- 6. PROCEDURES SEM COMMIT INTERNO (COMPATIBILIDADE COM DRIVERS PYTHON)
-- ==============================================================================
CREATE OR REPLACE PROCEDURE sc_operacao.sp_aprovar_relatorio(
    p_relatorio_id UUID,
    p_analista_id UUID,
    p_parecer TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_status_atual sc_operacao.ty_status_diario;
BEGIN
    SELECT status INTO v_status_atual
    FROM sc_operacao.tb_relatorio_viagem
    WHERE id = p_relatorio_id
    FOR UPDATE;

    IF v_status_atual IS NULL THEN
        RAISE EXCEPTION 'Operação Bloqueada: Relatório % não encontrado.', p_relatorio_id
        USING ERRCODE = 'P0004';
    END IF;

    IF v_status_atual != 'pendente' THEN
        RAISE EXCEPTION 'Operação Bloqueada: Apenas relatórios com status "pendente" podem ser aprovados. Status atual: %', v_status_atual
        USING ERRCODE = 'P0005';
    END IF;

    UPDATE sc_operacao.tb_relatorio_viagem
    SET status = 'aprovado'
    WHERE id = p_relatorio_id;

    INSERT INTO sc_operacao.tb_auditoria_analise (relatorio_id, analista_id, aprovado, parecer_tecnico)
    VALUES (p_relatorio_id, p_analista_id, TRUE, p_parecer);
END;
$$;

CREATE OR REPLACE PROCEDURE sc_operacao.sp_registrar_anomalia(
    p_relatorio_id UUID,
    p_tipo_etapa VARCHAR(20),
    p_codigo_anomalia VARCHAR(50),
    p_descricao_outros VARCHAR(150) DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_dominio_anomalia_id UUID;
BEGIN
    SELECT id INTO v_dominio_anomalia_id
    FROM sc_operacao.tb_dominio_anomalia
    WHERE codigo = p_codigo_anomalia
      AND tipo_etapa = p_tipo_etapa
      AND ativo = TRUE;

    IF v_dominio_anomalia_id IS NULL THEN
        RAISE EXCEPTION 'Operação Bloqueada: Código de anomalia "%" inválido, inativo ou não pertence à etapa de %.', p_codigo_anomalia, p_tipo_etapa
        USING ERRCODE = 'P0006';
    END IF;

    IF p_tipo_etapa = 'EMBARQUE' THEN
        INSERT INTO sc_operacao.tb_anomalia_embarque (relatorio_id, dominio_anomalia_id, descricao_outros)
        VALUES (p_relatorio_id, v_dominio_anomalia_id, p_descricao_outros);
    ELSIF p_tipo_etapa = 'DESEMBARQUE' THEN
        INSERT INTO sc_operacao.tb_anomalia_desembarque (relatorio_id, dominio_anomalia_id, descricao_outros)
        VALUES (p_relatorio_id, v_dominio_anomalia_id, p_descricao_outros);
    ELSE
        RAISE EXCEPTION 'Etapa inválida. Utilize "EMBARQUE" ou "DESEMBARQUE".'
        USING ERRCODE = 'P0007';
    END IF;
END;
$$;

COMMIT;
