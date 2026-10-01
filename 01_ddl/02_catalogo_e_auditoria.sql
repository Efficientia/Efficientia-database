BEGIN;

-- ==============================================================================
-- 1. GOVERNANÇA E METADADOS
-- ==============================================================================
CREATE TABLE sc_auditoria.tb_catalogo_dados
(
    id                    UUID        DEFAULT gen_random_uuid(),
    esquema_nome          VARCHAR(50) DEFAULT 'public',
    tabela_nome           VARCHAR(100) NOT NULL,
    coluna_nome           VARCHAR(100),
    descricao             TEXT         NOT NULL,
    regra_negocio_critica TEXT,
    nivel_acesso_leitura  VARCHAR(100) NOT NULL,
    nivel_acesso_escrita  VARCHAR(100) NOT NULL,
    atualizado_em         TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_catalogo_dados PRIMARY KEY (id)
);

CREATE TABLE sc_auditoria.tb_auditoria_log
(
    id             UUID        DEFAULT gen_random_uuid(),
    empresa_id     UUID,
    tabela_afetada VARCHAR(100) NOT NULL,
    operacao       VARCHAR(10)  NOT NULL,
    usuario_db     VARCHAR(100) NOT NULL,
    dados_antigos  JSONB,
    dados_novos    JSONB,
    data_hora      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_auditoria_log PRIMARY KEY (id)
);

COMMIT;