-- ==============================================================================
-- SUÍTE DE TESTES 01: REGRAS DE NEGÓCIO, ALOCAÇÃO DE FROTA E APROVAÇÃO
-- ==============================================================================

BEGIN;

DO $$
DECLARE
    v_empresa_id   UUID;
    v_motorista_id UUID;
    v_cavalo_id    UUID;
    v_carreta_id   UUID;
    v_fazenda_id   UUID;
    v_analista_id  UUID;
    v_relatorio_id UUID;
    v_erro_cnh     BOOLEAN := FALSE;
    v_erro_categ   BOOLEAN := FALSE;
BEGIN
    SELECT id INTO v_empresa_id FROM sc_corporativo.tb_empresa LIMIT 1;
    SELECT id INTO v_fazenda_id FROM sc_corporativo.tb_fazenda WHERE empresa_id = v_empresa_id LIMIT 1;
    SELECT id INTO v_cavalo_id FROM sc_frota.tb_veiculo_cavalo WHERE empresa_id = v_empresa_id LIMIT 1;
    SELECT id INTO v_carreta_id FROM sc_frota.tb_veiculo_carreta WHERE empresa_id = v_empresa_id LIMIT 1;
    SELECT id INTO v_analista_id FROM sc_corporativo.tb_usuario WHERE empresa_id = v_empresa_id AND tipo = 'analista' LIMIT 1;

    -- 1. Teste de bloqueio de condutor com CNH vencida
    INSERT INTO sc_corporativo.tb_usuario (
        empresa_id, tipo, cargo, nivel_acesso, cpf, cnh_numero, categoria_cnh, data_vencimento_cnh, nome_completo, senha_hash
    ) VALUES (
        v_empresa_id, 'motorista', 'Motorista Teste Vencido', 'conducao', '99988877700', '1122334455', 'e',
        CURRENT_DATE - INTERVAL '10 days', 'Condutor CNH Vencida', 'hash_teste'
    ) RETURNING id INTO v_motorista_id;

    BEGIN
        INSERT INTO sc_operacao.tb_relatorio_viagem (
            empresa_id, fazenda_id, motorista_id, manobrista_id, curraleiro_id,
            cavalo_id, carreta_id, capacidade_carga_utilizada
        ) VALUES (
            v_empresa_id, v_fazenda_id, v_motorista_id, v_analista_id, v_analista_id,
            v_cavalo_id, v_carreta_id, 35
        );
    EXCEPTION WHEN SQLSTATE 'P0001' THEN
        v_erro_cnh := TRUE;
    END;

    IF NOT v_erro_cnh THEN
        RAISE EXCEPTION 'Falha no teste: o sistema permitiu alocar motorista com CNH vencida.';
    END IF;

    -- 2. Teste de bloqueio de condutor sem categoria 'E' para carreta
    UPDATE sc_corporativo.tb_usuario
       SET data_vencimento_cnh = CURRENT_DATE + INTERVAL '1 year',
           categoria_cnh = 'b'
     WHERE id = v_motorista_id;

    BEGIN
        INSERT INTO sc_operacao.tb_relatorio_viagem (
            empresa_id, fazenda_id, motorista_id, manobrista_id, curraleiro_id,
            cavalo_id, carreta_id, capacidade_carga_utilizada
        ) VALUES (
            v_empresa_id, v_fazenda_id, v_motorista_id, v_analista_id, v_analista_id,
            v_cavalo_id, v_carreta_id, 35
        );
    EXCEPTION WHEN SQLSTATE 'P0004' THEN
        v_erro_categ := TRUE;
    END;

    IF NOT v_erro_categ THEN
        RAISE EXCEPTION 'Falha no teste: o sistema permitiu alocar motorista com categoria B para carreta boiadeira.';
    END IF;

    -- 3. Inserção válida com categoria 'E'
    UPDATE sc_corporativo.tb_usuario SET categoria_cnh = 'e' WHERE id = v_motorista_id;

    INSERT INTO sc_operacao.tb_relatorio_viagem (
        empresa_id, fazenda_id, motorista_id, manobrista_id, curraleiro_id,
        cavalo_id, carreta_id, capacidade_carga_utilizada, status
    ) VALUES (
        v_empresa_id, v_fazenda_id, v_motorista_id, v_analista_id, v_analista_id,
        v_cavalo_id, v_carreta_id, 35, 'pendente'
    ) RETURNING id INTO v_relatorio_id;

    -- 4. Teste de aprovação via procedure sp_aprovar_relatorio
    CALL sc_operacao.sp_aprovar_relatorio(
        v_relatorio_id,
        v_analista_id,
        TRUE,
        NULL,
        'Aprovação automática no teste de integridade.'
    );

    IF NOT EXISTS (
        SELECT 1 FROM sc_operacao.tb_relatorio_viagem
         WHERE id = v_relatorio_id AND status = 'aprovado'
    ) THEN
        RAISE EXCEPTION 'Falha no teste: o relatório não transitou para status aprovado.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM sc_operacao.tb_outbox_evento
         WHERE agregado_id = v_relatorio_id AND tipo_evento = 'relatorio.status_alterado'
    ) THEN
        RAISE EXCEPTION 'Falha no teste: evento Outbox não foi gerado na transição de status.';
    END IF;

    RAISE NOTICE 'Suíte 01 executada com 100%% de sucesso.';
END $$;

ROLLBACK;
