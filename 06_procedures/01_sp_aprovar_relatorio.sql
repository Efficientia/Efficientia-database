BEGIN;

CREATE
OR REPLACE PROCEDURE sc_operacao.sp_aprovar_relatorio(
    p_relatorio_id UUID,
    p_analista_id UUID,
    p_parecer TEXT
)
LANGUAGE plpgsql
AS $$
DECLARE
v_status_atual sc_operacao.ty_status_diario;
BEGIN
SELECT status
INTO v_status_atual
FROM sc_operacao.tb_relatorio_viagem
WHERE id = p_relatorio_id
    FOR UPDATE;

IF
v_status_atual IS NULL THEN
        RAISE EXCEPTION 'Operação Bloqueada: Relatório % não encontrado.', p_relatorio_id
        USING ERRCODE = 'P0004';
END IF;

    IF
v_status_atual != 'pendente' THEN
        RAISE EXCEPTION 'Operação Bloqueada: Apenas relatórios com status "pendente" podem ser aprovados. Status atual: %', v_status_atual
        USING ERRCODE = 'P0005';
END IF;

UPDATE sc_operacao.tb_relatorio_viagem
SET status = 'aprovado'
WHERE id = p_relatorio_id;

INSERT INTO sc_operacao.tb_auditoria_analise (relatorio_id,
                                              analista_id,
                                              aprovado,
                                              parecer_tecnico)
VALUES (p_relatorio_id,
        p_analista_id,
        TRUE,
        p_parecer);

COMMIT;
END;
$$;

COMMIT;