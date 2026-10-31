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
