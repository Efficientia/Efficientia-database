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