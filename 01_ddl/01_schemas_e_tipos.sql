BEGIN;

-- ==============================================================================
-- 1. SCHEMAS
-- ==============================================================================
CREATE SCHEMA sc_auditoria;
CREATE SCHEMA sc_corporativo;
CREATE SCHEMA sc_frota;
CREATE SCHEMA sc_operacao;

-- ==============================================================================
-- 2. EXTENSÕES
-- ==============================================================================
-- Habilita pgcrypto caso versões antigas precisem
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ==============================================================================
-- 3. ENUMS
-- ==============================================================================
CREATE TYPE sc_corporativo.ty_tipo_usuario AS ENUM ('administrador', 'motorista', 'manobrista', 'analista', 'pecuarista', 'curraleiro');
CREATE TYPE sc_corporativo.ty_nivel_acesso AS ENUM ('administrativo', 'auditoria', 'conducao');
CREATE TYPE sc_corporativo.ty_categoria_cnh AS ENUM ('a', 'b', 'c', 'd', 'e');
CREATE TYPE sc_operacao.ty_status_diario AS ENUM ('rascunho', 'pendente', 'aprovado', 'reprovado');

COMMIT;