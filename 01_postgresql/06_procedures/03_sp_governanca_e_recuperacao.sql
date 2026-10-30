BEGIN;

-- ==============================================================================
-- 1. SINCRONIZAÇÃO AUTOMÁTICA DO CATÁLOGO DE DADOS COM PG_CATALOG
-- ==============================================================================
CREATE OR REPLACE PROCEDURE sc_auditoria.sp_sincronizar_catalogo_dados(
    p_remover_orfaos BOOLEAN DEFAULT FALSE
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    -- Insere colunas locais (não herdadas) que existam fisicamente no banco mas ainda não constem no catálogo
    INSERT INTO sc_auditoria.tb_catalogo_dados (
        esquema_nome,
        tabela_nome,
        coluna_nome,
        descricao,
        regra_negocio_critica,
        nivel_acesso_leitura,
        nivel_acesso_escrita,
        dado_pessoal_lgpd
    )
    SELECT
        n.nspname,
        c.relname,
        a.attname,
        'Coluna catalogada automaticamente via introspecção de metadados (' ||
            pg_catalog.format_type(a.atttypid, a.atttypmod) || ').',
        'Pendente de revisão funcional pelo administrador de dados.',
        'auditoria'::sc_corporativo.ty_nivel_acesso,
        'administrativo'::sc_corporativo.ty_nivel_acesso,
        (a.attname IN ('cpf', 'cnh_numero', 'nome_completo', 'data_nascimento', 'email', 'telefone', 'senha_hash')
         OR a.attname LIKE 'url_assinatura_%')
    FROM pg_catalog.pg_class c
    INNER JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    INNER JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
    WHERE n.nspname IN ('sc_auditoria', 'sc_corporativo', 'sc_frota', 'sc_operacao')
      AND c.relkind = 'r'
      AND a.attnum > 0
      AND NOT a.attisdropped
      AND a.attinhcount = 0
    ON CONFLICT (esquema_nome, tabela_nome, coluna_nome) DO NOTHING;

    -- Opcionalmente remove metadados órfãos cujas colunas físicas não existam mais
    IF p_remover_orfaos THEN
        DELETE FROM sc_auditoria.tb_catalogo_dados cat
         WHERE NOT EXISTS (
             SELECT 1
               FROM pg_catalog.pg_class c
              INNER JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
              INNER JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
              WHERE n.nspname = cat.esquema_nome
                AND c.relname = cat.tabela_nome
                AND a.attname = cat.coluna_nome
                AND c.relkind = 'r'
                AND a.attnum > 0
                AND NOT a.attisdropped
         );
    END IF;
END;
$$;


-- ==============================================================================
-- 2. REGISTRO PADRONIZADO DE EVENTOS DE BACKUP E RESTAURAÇÃO
-- ==============================================================================
CREATE OR REPLACE PROCEDURE sc_auditoria.sp_registrar_evento_backup(
    p_operacao        VARCHAR(20),
    p_status          VARCHAR(20),
    p_nome_banco      VARCHAR(100),
    p_arquivo_dump    VARCHAR(255) DEFAULT NULL,
    p_tamanho_bytes   BIGINT       DEFAULT NULL,
    p_checksum_sha256 CHAR(64)     DEFAULT NULL,
    p_iniciado_em     TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP,
    p_finalizado_em   TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP,
    p_mensagem_erro   TEXT         DEFAULT NULL
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    INSERT INTO sc_auditoria.tb_historico_backup (
        operacao,
        status,
        nome_banco,
        arquivo_dump,
        tamanho_bytes,
        checksum_sha256,
        iniciado_em,
        finalizado_em,
        executado_por,
        mensagem_erro
    ) VALUES (
        p_operacao,
        p_status,
        p_nome_banco,
        p_arquivo_dump,
        p_tamanho_bytes,
        p_checksum_sha256,
        COALESCE(p_iniciado_em, CURRENT_TIMESTAMP),
        COALESCE(p_finalizado_em, CURRENT_TIMESTAMP),
        SESSION_USER,
        p_mensagem_erro
    );
END;
$$;


-- ==============================================================================
-- 3. RECUPERAÇÃO CIRÚRGICA DE LINHA A PARTIR DA TRILHA IMUTÁVEL JSONB
-- ==============================================================================
CREATE OR REPLACE PROCEDURE sc_auditoria.sp_restaurar_registro_auditoria(
    p_log_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
    v_log        sc_auditoria.tb_auditoria_log%ROWTYPE;
    v_relatorio  sc_operacao.tb_relatorio_viagem%ROWTYPE;
    v_config     sc_corporativo.tb_configuracao_operacao%ROWTYPE;
    v_usuario    sc_corporativo.tb_usuario%ROWTYPE;
    v_empresa    sc_corporativo.tb_empresa%ROWTYPE;
    v_id_alvo    UUID;
BEGIN
    SELECT *
      INTO v_log
      FROM sc_auditoria.tb_auditoria_log
     WHERE id = p_log_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Registro de auditoria (%) não localizado em tb_auditoria_log.', p_log_id
            USING ERRCODE = 'P0010';
    END IF;

    IF v_log.tabela_afetada NOT IN (
        'sc_operacao.tb_relatorio_viagem',
        'sc_corporativo.tb_configuracao_operacao',
        'sc_corporativo.tb_usuario',
        'sc_corporativo.tb_empresa'
    ) THEN
        RAISE EXCEPTION 'Tabela (%) não habilitada para restauração cirúrgica automatizada.', v_log.tabela_afetada
            USING ERRCODE = 'P0011';
    END IF;

    IF v_log.operacao IN ('UPDATE', 'DELETE') AND v_log.dados_antigos IS NULL THEN
        RAISE EXCEPTION 'O evento de auditoria (%) não contém snapshot anterior (dados_antigos) para reversão.', p_log_id
            USING ERRCODE = 'P0012';
    END IF;

    IF v_log.operacao = 'INSERT' AND v_log.dados_novos IS NULL THEN
        RAISE EXCEPTION 'O evento de auditoria (%) não contém snapshot inserido (dados_novos) para estorno.', p_log_id
            USING ERRCODE = 'P0012';
    END IF;

    -- Caso 1: Reverter um INSERT significa remover o registro inserido indevidamente
    IF v_log.operacao = 'INSERT' THEN
        v_id_alvo := (v_log.dados_novos->>'id')::UUID;
        CASE v_log.tabela_afetada
            WHEN 'sc_operacao.tb_relatorio_viagem' THEN
                DELETE FROM sc_operacao.tb_relatorio_viagem WHERE id = v_id_alvo;
            WHEN 'sc_corporativo.tb_configuracao_operacao' THEN
                DELETE FROM sc_corporativo.tb_configuracao_operacao WHERE id = v_id_alvo;
            WHEN 'sc_corporativo.tb_usuario' THEN
                DELETE FROM sc_corporativo.tb_usuario WHERE id = v_id_alvo;
            WHEN 'sc_corporativo.tb_empresa' THEN
                DELETE FROM sc_corporativo.tb_empresa WHERE id = v_id_alvo;
        END CASE;

    -- Caso 2: Reverter UPDATE ou DELETE recria/atualiza o estado anterior a partir de dados_antigos
    ELSIF v_log.tabela_afetada = 'sc_operacao.tb_relatorio_viagem' THEN
        v_relatorio := jsonb_populate_record(NULL::sc_operacao.tb_relatorio_viagem, v_log.dados_antigos);
        INSERT INTO sc_operacao.tb_relatorio_viagem VALUES (v_relatorio.*)
        ON CONFLICT (id) DO UPDATE SET
            empresa_id                 = EXCLUDED.empresa_id,
            status                     = EXCLUDED.status,
            fazenda_id                 = EXCLUDED.fazenda_id,
            motorista_id               = EXCLUDED.motorista_id,
            manobrista_id              = EXCLUDED.manobrista_id,
            curraleiro_id              = EXCLUDED.curraleiro_id,
            cavalo_id                  = EXCLUDED.cavalo_id,
            carreta_id                 = EXCLUDED.carreta_id,
            numero_gta                 = EXCLUDED.numero_gta,
            numero_nota_fiscal         = EXCLUDED.numero_nota_fiscal,
            capacidade_carga_utilizada = EXCLUDED.capacidade_carga_utilizada,
            data_embarque              = EXCLUDED.data_embarque,
            horario_embarque           = EXCLUDED.horario_embarque,
            horario_saida_propriedade  = EXCLUDED.horario_saida_propriedade,
            km_saida_embarcadouro      = EXCLUDED.km_saida_embarcadouro,
            data_chegada_unidade       = EXCLUDED.data_chegada_unidade,
            horario_chegada_unidade    = EXCLUDED.horario_chegada_unidade,
            horario_desembarque        = EXCLUDED.horario_desembarque,
            km_chegada_desembarcadouro = EXCLUDED.km_chegada_desembarcadouro,
            numero_curral              = EXCLUDED.numero_curral,
            sirene_re_funcionou        = EXCLUDED.sirene_re_funcionou,
            qtd_machos                 = EXCLUDED.qtd_machos,
            qtd_femeas                 = EXCLUDED.qtd_femeas,
            qtd_marrucos               = EXCLUDED.qtd_marrucos,
            qtd_em_pe                  = EXCLUDED.qtd_em_pe,
            qtd_deitado                = EXCLUDED.qtd_deitado,
            qtd_morto                  = EXCLUDED.qtd_morto,
            qtd_emergencia             = EXCLUDED.qtd_emergencia,
            url_laudo_mortalidade      = EXCLUDED.url_laudo_mortalidade,
            motivo_emergencia          = EXCLUDED.motivo_emergencia,
            comentarios                = EXCLUDED.comentarios,
            url_assinatura_pecuarista  = EXCLUDED.url_assinatura_pecuarista,
            url_assinatura_motorista   = EXCLUDED.url_assinatura_motorista,
            url_assinatura_manobrista  = EXCLUDED.url_assinatura_manobrista,
            url_assinatura_curraleiro  = EXCLUDED.url_assinatura_curraleiro,
            criado_em                  = EXCLUDED.criado_em,
            enviado_em                 = EXCLUDED.enviado_em;

    ELSIF v_log.tabela_afetada = 'sc_corporativo.tb_configuracao_operacao' THEN
        v_config := jsonb_populate_record(NULL::sc_corporativo.tb_configuracao_operacao, v_log.dados_antigos);
        INSERT INTO sc_corporativo.tb_configuracao_operacao VALUES (v_config.*)
        ON CONFLICT (id) DO UPDATE SET
            empresa_id                     = EXCLUDED.empresa_id,
            tempo_max_viagem_horas         = EXCLUDED.tempo_max_viagem_horas,
            mortalidade_bloqueio_cabecas   = EXCLUDED.mortalidade_bloqueio_cabecas,
            prazo_analise_horas            = EXCLUDED.prazo_analise_horas,
            meta_mortalidade               = EXCLUDED.meta_mortalidade,
            qtd_assinaturas_obrigatorias   = EXCLUDED.qtd_assinaturas_obrigatorias,
            alerta_sirene_re               = EXCLUDED.alerta_sirene_re,
            alerta_inspecao_dias           = EXCLUDED.alerta_inspecao_dias,
            alerta_cnh_vencida             = EXCLUDED.alerta_cnh_vencida,
            alerta_tempo_parada_imprevista = EXCLUDED.alerta_tempo_parada_imprevista,
            atualizado_em                  = CURRENT_TIMESTAMP;

    ELSIF v_log.tabela_afetada = 'sc_corporativo.tb_usuario' THEN
        v_usuario := jsonb_populate_record(NULL::sc_corporativo.tb_usuario, v_log.dados_antigos);
        -- Como fn_registrar_auditoria omite senha_hash por segurança, definimos marcador de bloqueio caso seja restauração de DELETE
        v_usuario.senha_hash := COALESCE(v_usuario.senha_hash, 'REDEFINICAO_OBRIGATORIA_POS_RESTAURACAO');
        INSERT INTO sc_corporativo.tb_usuario VALUES (v_usuario.*)
        ON CONFLICT (id) DO UPDATE SET
            empresa_id           = EXCLUDED.empresa_id,
            tipo                 = EXCLUDED.tipo,
            cargo                = EXCLUDED.cargo,
            nivel_acesso         = EXCLUDED.nivel_acesso,
            cpf                  = EXCLUDED.cpf,
            cnh_numero           = EXCLUDED.cnh_numero,
            categoria_cnh        = EXCLUDED.categoria_cnh,
            data_vencimento_cnh  = EXCLUDED.data_vencimento_cnh,
            nome_completo        = EXCLUDED.nome_completo,
            data_nascimento      = EXCLUDED.data_nascimento,
            email                = EXCLUDED.email,
            telefone             = EXCLUDED.telefone,
            url_assinatura_geral = EXCLUDED.url_assinatura_geral,
            status_cadastro      = EXCLUDED.status_cadastro;

    ELSIF v_log.tabela_afetada = 'sc_corporativo.tb_empresa' THEN
        v_empresa := jsonb_populate_record(NULL::sc_corporativo.tb_empresa, v_log.dados_antigos);
        INSERT INTO sc_corporativo.tb_empresa VALUES (v_empresa.*)
        ON CONFLICT (id) DO UPDATE SET
            endereco_id    = EXCLUDED.endereco_id,
            nome           = EXCLUDED.nome,
            razao_social   = EXCLUDED.razao_social,
            codigo_interno = EXCLUDED.codigo_interno,
            email          = EXCLUDED.email,
            cnpj           = EXCLUDED.cnpj;
    END IF;

    -- Registra a restauração cirúrgica no histórico oficial de recuperação
    CALL sc_auditoria.sp_registrar_evento_backup(
        'RESTORE_AUDITORIA',
        'SUCESSO',
        current_database(),
        'log_auditoria:' || p_log_id::TEXT,
        octet_length(COALESCE(v_log.dados_antigos, v_log.dados_novos)::TEXT)::BIGINT,
        NULL,
        CURRENT_TIMESTAMP,
        CURRENT_TIMESTAMP,
        NULL
    );
END;
$$;

COMMIT;
