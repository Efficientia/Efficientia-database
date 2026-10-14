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