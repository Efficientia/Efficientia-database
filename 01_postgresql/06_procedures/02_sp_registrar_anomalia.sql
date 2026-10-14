BEGIN;

CREATE
OR REPLACE PROCEDURE sc_operacao.sp_registrar_anomalia(
    p_relatorio_id UUID,
    p_tipo_etapa VARCHAR(20), -- 'EMBARQUE' ou 'DESEMBARQUE'
    p_codigo_anomalia VARCHAR(50),
    p_descricao_outros VARCHAR(150) DEFAULT NULL
)
LANGUAGE plpgsql
AS $$
DECLARE
v_dominio_anomalia_id UUID;
BEGIN
SELECT id
INTO v_dominio_anomalia_id
FROM sc_operacao.tb_dominio_anomalia
WHERE codigo = p_codigo_anomalia
  AND tipo_etapa = p_tipo_etapa
  AND ativo = TRUE;

IF
v_dominio_anomalia_id IS NULL THEN
        RAISE EXCEPTION 'Operação Bloqueada: Código de anomalia "%" inválido, inativo ou não pertence à etapa de %.', p_codigo_anomalia, p_tipo_etapa
        USING ERRCODE = 'P0006';
END IF;

    IF
p_tipo_etapa = 'EMBARQUE' THEN
        INSERT INTO sc_operacao.tb_anomalia_embarque (
            relatorio_id,
            dominio_anomalia_id,
            descricao_outros
        ) VALUES (
            p_relatorio_id,
            v_dominio_anomalia_id,
            p_descricao_outros
        );

    ELSIF
p_tipo_etapa = 'DESEMBARQUE' THEN
        INSERT INTO sc_operacao.tb_anomalia_desembarque (
            relatorio_id,
            dominio_anomalia_id,
            descricao_outros
        ) VALUES (
            p_relatorio_id,
            v_dominio_anomalia_id,
            p_descricao_outros
        );

ELSE
        RAISE EXCEPTION 'Etapa inválida. Utilize "EMBARQUE" ou "DESEMBARQUE".'
        USING ERRCODE = 'P0007';
END IF;

COMMIT;
END;
$$;

COMMIT;