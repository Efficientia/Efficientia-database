BEGIN;

-- ==============================================================================
-- 1. EVOLUÇÃO DE GOVERNANÇA E LGPD NO CATÁLOGO DE DADOS
-- ==============================================================================
ALTER TABLE sc_auditoria.tb_catalogo_dados
    ADD COLUMN IF NOT EXISTS dado_pessoal_lgpd BOOLEAN NOT NULL DEFAULT FALSE;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uk_catalogo_esquema_tabela_coluna'
    ) THEN
        ALTER TABLE sc_auditoria.tb_catalogo_dados
            ADD CONSTRAINT uk_catalogo_esquema_tabela_coluna
            UNIQUE (esquema_nome, tabela_nome, coluna_nome);
    END IF;
END $$;

-- ==============================================================================
-- 2. HISTÓRICO DE BACKUP E RECUPERAÇÃO DE DESASTRES
-- ==============================================================================
CREATE TABLE IF NOT EXISTS sc_auditoria.tb_historico_backup
(
    id              UUID         DEFAULT gen_random_uuid(),
    operacao        VARCHAR(20)  NOT NULL,
    status          VARCHAR(20)  NOT NULL,
    nome_banco      VARCHAR(100) NOT NULL,
    arquivo_dump    VARCHAR(255),
    tamanho_bytes   BIGINT,
    checksum_sha256 CHAR(64),
    iniciado_em     TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finalizado_em   TIMESTAMPTZ,
    executado_por   VARCHAR(100) NOT NULL DEFAULT SESSION_USER,
    mensagem_erro   TEXT,
    CONSTRAINT pk_historico_backup PRIMARY KEY (id),
    CONSTRAINT ck_backup_operacao CHECK (operacao IN ('BACKUP', 'RESTORE', 'RESTORE_AUDITORIA')),
    CONSTRAINT ck_backup_status CHECK (status IN ('SUCESSO', 'FALHA')),
    CONSTRAINT ck_backup_tamanho CHECK (tamanho_bytes IS NULL OR tamanho_bytes >= 0),
    CONSTRAINT ck_backup_datas CHECK (finalizado_em IS NULL OR finalizado_em >= iniciado_em)
);

-- ==============================================================================
-- 3. AUTORRELACIONAMENTO HIERÁRQUICO NO CATÁLOGO DE ANOMALIAS (CTE RECURSIVA)
-- ==============================================================================
ALTER TABLE sc_operacao.tb_dominio_anomalia
    ADD COLUMN IF NOT EXISTS anomalia_pai_id UUID;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_dominio_anomalia_pai'
    ) THEN
        ALTER TABLE sc_operacao.tb_dominio_anomalia
            ADD CONSTRAINT fk_dominio_anomalia_pai
            FOREIGN KEY (anomalia_pai_id)
            REFERENCES sc_operacao.tb_dominio_anomalia (id)
            ON DELETE RESTRICT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_anomalia_sem_auto_referencia'
    ) THEN
        ALTER TABLE sc_operacao.tb_dominio_anomalia
            ADD CONSTRAINT ck_anomalia_sem_auto_referencia
            CHECK (anomalia_pai_id IS NULL OR anomalia_pai_id <> id);
    END IF;
END $$;

COMMIT;
