BEGIN;

CREATE
OR REPLACE FUNCTION sc_auditoria.fn_registrar_auditoria()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
v_empresa_id UUID;
    v_dados_row
JSONB;
BEGIN
    IF
TG_OP = 'DELETE' THEN
        v_dados_row := row_to_json(OLD)::JSONB;
ELSE
        v_dados_row := row_to_json(NEW)::JSONB;
END IF;

BEGIN
        v_empresa_id
:= (v_dados_row->>'empresa_id')::UUID;
EXCEPTION WHEN OTHERS THEN
        v_empresa_id := NULL;
END;

INSERT INTO sc_auditoria.tb_auditoria_log (empresa_id,
                                           tabela_afetada,
                                           operacao,
                                           usuario_db,
                                           dados_antigos,
                                           dados_novos)
VALUES (v_empresa_id,
        TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
        TG_OP,
        SESSION_USER,
        CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN row_to_json(OLD)::JSONB ELSE NULL END,
        CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN row_to_json(NEW)::JSONB ELSE NULL END);

IF
TG_OP = 'DELETE' THEN
        RETURN OLD;
END IF;
RETURN NEW;
END;
$$;

COMMIT;