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
