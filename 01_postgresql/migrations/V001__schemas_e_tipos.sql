BEGIN;

-- ==============================================================================
-- 1. SCHEMAS
-- ==============================================================================
CREATE SCHEMA IF NOT EXISTS sc_auditoria;
CREATE SCHEMA IF NOT EXISTS sc_corporativo;
CREATE SCHEMA IF NOT EXISTS sc_frota;
CREATE SCHEMA IF NOT EXISTS sc_operacao;

-- ==============================================================================
-- 2. EXTENSÕES
-- ==============================================================================
-- Habilita pgcrypto caso versões antigas precisem
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==============================================================================
-- 3. ENUMS (IDEMPOTENTES)
-- ==============================================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'sc_corporativo' AND t.typname = 'ty_tipo_usuario'
    ) THEN
        CREATE TYPE sc_corporativo.ty_tipo_usuario AS ENUM ('administrador', 'motorista', 'manobrista', 'analista', 'pecuarista', 'curraleiro');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'sc_corporativo' AND t.typname = 'ty_nivel_acesso'
    ) THEN
        CREATE TYPE sc_corporativo.ty_nivel_acesso AS ENUM ('administrativo', 'auditoria', 'conducao');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'sc_corporativo' AND t.typname = 'ty_categoria_cnh'
    ) THEN
        CREATE TYPE sc_corporativo.ty_categoria_cnh AS ENUM ('a', 'b', 'c', 'd', 'e');
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type t
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'sc_operacao' AND t.typname = 'ty_status_diario'
    ) THEN
        CREATE TYPE sc_operacao.ty_status_diario AS ENUM ('rascunho', 'pendente', 'aprovado', 'reprovado');
    END IF;
END $$;

COMMIT;
