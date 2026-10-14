BEGIN;

-- ==============================================================================
-- 1. DIÁRIO DE ROTA
-- ==============================================================================
CREATE TABLE sc_operacao.tb_relatorio_viagem
(
    id                         UUID                                  DEFAULT gen_random_uuid(),
    empresa_id                 UUID                         NOT NULL,
    status                     sc_operacao.ty_status_diario NOT NULL DEFAULT 'rascunho',

    fazenda_id                 UUID                         NOT NULL,
    motorista_id               UUID                         NOT NULL,
    manobrista_id              UUID                         NOT NULL,
    curraleiro_id              UUID                         NOT NULL,
    cavalo_id                  UUID                         NOT NULL,
    carreta_id                 UUID                         NOT NULL,

    numero_gta                 VARCHAR(50),
    numero_nota_fiscal         VARCHAR(50),
    capacidade_carga_utilizada INTEGER                      NOT NULL,

    data_embarque              DATE,
    horario_embarque           TIME WITH TIME ZONE,
    horario_saida_propriedade  TIME WITH TIME ZONE,
    km_saida_embarcadouro      INTEGER,

    data_chegada_unidade       DATE,
    horario_chegada_unidade    TIME WITH TIME ZONE,
    horario_desembarque        TIME WITH TIME ZONE,
    km_chegada_desembarcadouro INTEGER,
    numero_curral              VARCHAR(20),
    sirene_re_funcionou        BOOLEAN,

    qtd_machos                 INTEGER                      NOT NULL DEFAULT 0,
    qtd_femeas                 INTEGER                      NOT NULL DEFAULT 0,
    qtd_marrucos               INTEGER                      NOT NULL DEFAULT 0,
    qtd_em_pe                  INTEGER                      NOT NULL DEFAULT 0,
    qtd_deitado                INTEGER                      NOT NULL DEFAULT 0,
    qtd_morto                  INTEGER                      NOT NULL DEFAULT 0,
    qtd_emergencia             INTEGER                      NOT NULL DEFAULT 0,

    url_laudo_mortalidade      TEXT,
    motivo_emergencia          TEXT,
    comentarios                TEXT,

    url_assinatura_pecuarista  TEXT,
    url_assinatura_motorista   TEXT,
    url_assinatura_manobrista  TEXT,
    url_assinatura_curraleiro  TEXT,

    criado_em                  TIMESTAMPTZ                           DEFAULT CURRENT_TIMESTAMP,
    enviado_em                 TIMESTAMPTZ,

    CONSTRAINT pk_relatorio_viagem PRIMARY KEY (id),
    CONSTRAINT uk_relatorio_gta UNIQUE (numero_gta),

    CONSTRAINT fk_relatorio_empresa FOREIGN KEY (empresa_id) REFERENCES sc_corporativo.tb_empresa (id) ON DELETE RESTRICT,
    CONSTRAINT fk_relatorio_fazenda FOREIGN KEY (fazenda_id) REFERENCES sc_corporativo.tb_fazenda (id) ON DELETE RESTRICT,
    CONSTRAINT fk_relatorio_motorista FOREIGN KEY (motorista_id) REFERENCES sc_corporativo.tb_usuario (id) ON DELETE RESTRICT,
    CONSTRAINT fk_relatorio_manobrista FOREIGN KEY (manobrista_id) REFERENCES sc_corporativo.tb_usuario (id) ON DELETE RESTRICT,
    CONSTRAINT fk_relatorio_curraleiro FOREIGN KEY (curraleiro_id) REFERENCES sc_corporativo.tb_usuario (id) ON DELETE RESTRICT,
    CONSTRAINT fk_relatorio_cavalo FOREIGN KEY (cavalo_id) REFERENCES sc_frota.tb_veiculo_cavalo (id) ON DELETE RESTRICT,
    CONSTRAINT fk_relatorio_carreta FOREIGN KEY (carreta_id) REFERENCES sc_frota.tb_veiculo_carreta (id) ON DELETE RESTRICT
);

-- ==============================================================================
-- 2. OPERAÇÃO
-- ==============================================================================
CREATE TABLE sc_operacao.tb_parada_imprevista
(
    id                UUID DEFAULT gen_random_uuid(),
    relatorio_id      UUID        NOT NULL,
    dominio_parada_id UUID        NOT NULL,
    data_hora_inicio  TIMESTAMPTZ NOT NULL,
    data_hora_fim     TIMESTAMPTZ NOT NULL,
    CONSTRAINT pk_parada_imprevista PRIMARY KEY (id),
    CONSTRAINT fk_parada_relatorio FOREIGN KEY (relatorio_id) REFERENCES sc_operacao.tb_relatorio_viagem (id) ON DELETE CASCADE,
    CONSTRAINT fk_parada_dominio FOREIGN KEY (dominio_parada_id) REFERENCES sc_operacao.tb_dominio_motivo_parada (id) ON DELETE RESTRICT,
    CONSTRAINT ck_parada_datas CHECK (data_hora_fim > data_hora_inicio)
);

CREATE TABLE sc_operacao.tb_anomalia_embarque
(
    id                  UUID DEFAULT gen_random_uuid(),
    relatorio_id        UUID NOT NULL,
    dominio_anomalia_id UUID NOT NULL,
    descricao_outros    VARCHAR(150),
    CONSTRAINT pk_anomalia_embarque PRIMARY KEY (id),
    CONSTRAINT fk_ano_emb_relatorio FOREIGN KEY (relatorio_id) REFERENCES sc_operacao.tb_relatorio_viagem (id) ON DELETE CASCADE,
    CONSTRAINT fk_ano_emb_dominio FOREIGN KEY (dominio_anomalia_id) REFERENCES sc_operacao.tb_dominio_anomalia (id) ON DELETE RESTRICT
);

CREATE TABLE sc_operacao.tb_anomalia_desembarque
(
    id                  UUID DEFAULT gen_random_uuid(),
    relatorio_id        UUID NOT NULL,
    dominio_anomalia_id UUID NOT NULL,
    descricao_outros    VARCHAR(150),
    CONSTRAINT pk_anomalia_desembarque PRIMARY KEY (id),
    CONSTRAINT fk_ano_des_relatorio FOREIGN KEY (relatorio_id) REFERENCES sc_operacao.tb_relatorio_viagem (id) ON DELETE CASCADE,
    CONSTRAINT fk_ano_des_dominio FOREIGN KEY (dominio_anomalia_id) REFERENCES sc_operacao.tb_dominio_anomalia (id) ON DELETE RESTRICT
);

CREATE TABLE sc_operacao.tb_auditoria_analise
(
    id                UUID                 DEFAULT gen_random_uuid(),
    relatorio_id      UUID        NOT NULL,
    analista_id       UUID        NOT NULL,
    data_hora_analise TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    aprovado          BOOLEAN     NOT NULL,
    motivo_rejeicao   VARCHAR(255),
    parecer_tecnico   TEXT,
    CONSTRAINT pk_auditoria_analise PRIMARY KEY (id),
    CONSTRAINT fk_aud_analise_relatorio FOREIGN KEY (relatorio_id) REFERENCES sc_operacao.tb_relatorio_viagem (id) ON DELETE CASCADE,
    CONSTRAINT fk_aud_analise_usuario FOREIGN KEY (analista_id) REFERENCES sc_corporativo.tb_usuario (id) ON DELETE RESTRICT
);

COMMIT;