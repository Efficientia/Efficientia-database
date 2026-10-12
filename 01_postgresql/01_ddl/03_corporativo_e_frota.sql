BEGIN;

-- ==============================================================================
-- 1. TABELAS CORPORATIVAS BASE
-- ==============================================================================
CREATE TABLE sc_corporativo.tb_endereco
(
    id         UUID DEFAULT gen_random_uuid(),
    cep        VARCHAR(10)  NOT NULL,
    logradouro VARCHAR(150) NOT NULL,
    numero     VARCHAR(20)  NOT NULL,
    cidade     VARCHAR(100) NOT NULL,
    estado     VARCHAR(2)   NOT NULL,
    CONSTRAINT pk_endereco PRIMARY KEY (id)
);

CREATE TABLE sc_corporativo.tb_empresa
(
    id             UUID DEFAULT gen_random_uuid(),
    endereco_id    UUID        NOT NULL,
    nome           VARCHAR(150),
    razao_social   VARCHAR(150),
    codigo_interno VARCHAR(20) NOT NULL,
    email          VARCHAR(150),
    cnpj           VARCHAR(14) NOT NULL,
    CONSTRAINT pk_empresa PRIMARY KEY (id),
    CONSTRAINT uk_empresa_email UNIQUE (email),
    CONSTRAINT uk_empresa_cnpj UNIQUE (cnpj),
    CONSTRAINT fk_empresa_endereco FOREIGN KEY (endereco_id) REFERENCES sc_corporativo.tb_endereco (id) ON DELETE RESTRICT
);

CREATE TABLE sc_corporativo.tb_configuracao_operacao
(
    id                             UUID                   DEFAULT gen_random_uuid(),
    empresa_id                     UUID          NOT NULL,
    tempo_max_viagem_horas         INTEGER       NOT NULL DEFAULT 8,
    mortalidade_bloqueio_cabecas   INTEGER       NOT NULL DEFAULT 1,
    prazo_analise_horas            INTEGER       NOT NULL DEFAULT 24,
    meta_mortalidade               NUMERIC(5, 2) NOT NULL DEFAULT 0.50,
    qtd_assinaturas_obrigatorias   INTEGER       NOT NULL DEFAULT 4,
    alerta_sirene_re               BOOLEAN       NOT NULL DEFAULT TRUE,
    alerta_inspecao_dias           INTEGER       NOT NULL DEFAULT 15,
    alerta_cnh_vencida             BOOLEAN       NOT NULL DEFAULT TRUE,
    alerta_tempo_parada_imprevista INTEGER       NOT NULL DEFAULT 60,
    atualizado_em                  TIMESTAMPTZ            DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_configuracao PRIMARY KEY (id),
    CONSTRAINT uk_configuracao_empresa UNIQUE (empresa_id),
    CONSTRAINT fk_configuracao_empresa FOREIGN KEY (empresa_id) REFERENCES sc_corporativo.tb_empresa (id) ON DELETE CASCADE,
    CONSTRAINT ck_config_meta_mortalidade CHECK (meta_mortalidade >= 0 AND meta_mortalidade <= 100)
);

CREATE TABLE sc_corporativo.tb_usuario
(
    id                   UUID                                    DEFAULT gen_random_uuid(),
    empresa_id           UUID                           NOT NULL,
    tipo                 sc_corporativo.ty_tipo_usuario NOT NULL,
    cargo                VARCHAR(150)                   NOT NULL,
    nivel_acesso         sc_corporativo.ty_nivel_acesso NOT NULL DEFAULT 'conducao',
    cpf                  VARCHAR(11)                    NOT NULL,
    cnh_numero           VARCHAR(20),
    categoria_cnh        sc_corporativo.ty_categoria_cnh,
    data_vencimento_cnh  DATE,
    nome_completo        VARCHAR(250)                   NOT NULL,
    data_nascimento      DATE,
    email                VARCHAR(150),
    telefone             VARCHAR(20),
    senha_hash           VARCHAR(255)                   NOT NULL,
    url_assinatura_geral TEXT,
    status_cadastro      VARCHAR(20)                    NOT NULL DEFAULT 'ativo',
    CONSTRAINT pk_usuario PRIMARY KEY (id),
    CONSTRAINT uk_usuario_cpf UNIQUE (cpf),
    CONSTRAINT uk_usuario_email UNIQUE (email),
    CONSTRAINT fk_usuario_empresa FOREIGN KEY (empresa_id) REFERENCES sc_corporativo.tb_empresa (id) ON DELETE CASCADE
);

CREATE TABLE sc_auditoria.tb_monitoramento_dau
(
    id          UUID          DEFAULT gen_random_uuid(),
    usuario_id  UUID NOT NULL,
    data_acesso DATE NOT NULL DEFAULT CURRENT_DATE,
    CONSTRAINT pk_monitoramento_dau PRIMARY KEY (id),
    CONSTRAINT uk_dau_usuario_data UNIQUE (usuario_id, data_acesso),
    CONSTRAINT fk_dau_usuario FOREIGN KEY (usuario_id) REFERENCES sc_corporativo.tb_usuario (id) ON DELETE CASCADE
);

-- ==============================================================================
-- 2. TABELAS DOMÍNIO
-- ==============================================================================
CREATE TABLE sc_operacao.tb_dominio_motivo_parada
(
    id        UUID    DEFAULT gen_random_uuid(),
    codigo    VARCHAR(50)  NOT NULL,
    descricao VARCHAR(150) NOT NULL,
    ativo     BOOLEAN DEFAULT TRUE,
    CONSTRAINT pk_dominio_parada PRIMARY KEY (id),
    CONSTRAINT uk_dominio_parada_codigo UNIQUE (codigo)
);

CREATE TABLE sc_operacao.tb_dominio_anomalia
(
    id         UUID    DEFAULT gen_random_uuid(),
    tipo_etapa VARCHAR(20)  NOT NULL, -- 'EMBARQUE' ou 'DESEMBARQUE'
    codigo     VARCHAR(50)  NOT NULL,
    descricao  VARCHAR(150) NOT NULL,
    ativo      BOOLEAN DEFAULT TRUE,
    CONSTRAINT pk_dominio_anomalia PRIMARY KEY (id),
    CONSTRAINT uk_dominio_anomalia_codigo UNIQUE (tipo_etapa, codigo),
    CONSTRAINT ck_anomalia_etapa CHECK (tipo_etapa IN ('EMBARQUE', 'DESEMBARQUE'))
);

-- ==============================================================================
-- 3. FROTA
-- ==============================================================================
CREATE TABLE sc_frota.tb_veiculo_base
(
    id                       UUID    DEFAULT gen_random_uuid(),
    empresa_id               UUID       NOT NULL,
    placa                    VARCHAR(7) NOT NULL,
    ativo                    BOOLEAN DEFAULT TRUE,
    data_vencimento_inspecao DATE       NOT NULL,
    CONSTRAINT pk_veiculo_base PRIMARY KEY (id),
    CONSTRAINT uk_veiculo_base_placa UNIQUE (placa),
    CONSTRAINT fk_veiculo_base_empresa FOREIGN KEY (empresa_id) REFERENCES sc_corporativo.tb_empresa (id) ON DELETE CASCADE
);

CREATE TABLE sc_frota.tb_veiculo_cavalo
(
    km_acumulado INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT pk_veiculo_cavalo PRIMARY KEY (id),
    CONSTRAINT uk_veiculo_cavalo_placa UNIQUE (placa),
    CONSTRAINT fk_veiculo_cavalo_empresa FOREIGN KEY (empresa_id) REFERENCES sc_corporativo.tb_empresa (id) ON DELETE CASCADE
) INHERITS (sc_frota.tb_veiculo_base);

CREATE TABLE sc_frota.tb_veiculo_carreta
(
    capacidade_cabecas INTEGER NOT NULL,
    CONSTRAINT pk_veiculo_carreta PRIMARY KEY (id),
    CONSTRAINT uk_veiculo_carreta_placa UNIQUE (placa),
    CONSTRAINT fk_veiculo_carreta_empresa FOREIGN KEY (empresa_id) REFERENCES sc_corporativo.tb_empresa (id) ON DELETE CASCADE,
    CONSTRAINT ck_carreta_capacidade CHECK (capacidade_cabecas > 0)
) INHERITS (sc_frota.tb_veiculo_base);

-- ==============================================================================
-- 4. ENTIDADES RELACIONAIS
-- ==============================================================================
CREATE TABLE sc_corporativo.tb_fazenda
(
    id            UUID DEFAULT gen_random_uuid(),
    empresa_id    UUID         NOT NULL,
    pecuarista_id UUID         NOT NULL,
    endereco_id   UUID         NOT NULL,
    nome          VARCHAR(150) NOT NULL,
    razao_social  VARCHAR(150),
    cnpj          VARCHAR(14),
    CONSTRAINT pk_fazenda PRIMARY KEY (id),
    CONSTRAINT uk_fazenda_cnpj UNIQUE (cnpj),
    CONSTRAINT fk_fazenda_empresa FOREIGN KEY (empresa_id) REFERENCES sc_corporativo.tb_empresa (id) ON DELETE CASCADE,
    CONSTRAINT fk_fazenda_pecuarista FOREIGN KEY (pecuarista_id) REFERENCES sc_corporativo.tb_usuario (id) ON DELETE RESTRICT,
    CONSTRAINT fk_fazenda_endereco FOREIGN KEY (endereco_id) REFERENCES sc_corporativo.tb_endereco (id) ON DELETE RESTRICT
);

CREATE TABLE sc_corporativo.tb_unidade_frigorifica
(
    id          UUID                  DEFAULT gen_random_uuid(),
    empresa_id  UUID         NOT NULL,
    analista_id UUID         NOT NULL,
    endereco_id UUID         NOT NULL,
    nome        VARCHAR(150) NOT NULL,
    cnpj        VARCHAR(14)  NOT NULL,
    qtd_currais INTEGER      NOT NULL DEFAULT 0,
    CONSTRAINT pk_unidade_frigorifica PRIMARY KEY (id),
    CONSTRAINT uk_unidade_cnpj UNIQUE (cnpj),
    CONSTRAINT fk_unidade_empresa FOREIGN KEY (empresa_id) REFERENCES sc_corporativo.tb_empresa (id) ON DELETE CASCADE,
    CONSTRAINT fk_unidade_analista FOREIGN KEY (analista_id) REFERENCES sc_corporativo.tb_usuario (id) ON DELETE RESTRICT,
    CONSTRAINT fk_unidade_endereco FOREIGN KEY (endereco_id) REFERENCES sc_corporativo.tb_endereco (id) ON DELETE RESTRICT
);

COMMIT;