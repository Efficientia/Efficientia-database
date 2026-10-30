#!/usr/bin/env bash
# ==============================================================================
# PROJETO EFFICIENTIA - SCRIPT DE RESTAURAÇÃO E RECUPERAÇÃO DE DESASTRES
# ==============================================================================
# Valida a integridade criptográfica SHA-256 do arquivo de despejo, executa
# a restauração via pg_restore em modo limpo (--clean --if-exists) e registra
# o evento na governança de auditoria (sc_auditoria.tb_historico_backup).
# ==============================================================================

set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Uso: $0 <caminho_do_arquivo_dump>"
    echo "Exemplo: $0 ./backups/efficientia_backup_20261029_020000.dump"
    exit 1
fi

ARQUIVO_DUMP="$1"

if [ ! -f "${ARQUIVO_DUMP}" ]; then
    echo "[ERRO] Arquivo de backup não encontrado: ${ARQUIVO_DUMP}" >&2
    exit 1
fi

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-efficientia}"

HORA_INICIO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TAMANHO_BYTES=$(stat -c%s "${ARQUIVO_DUMP}" 2>/dev/null || stat -f%z "${ARQUIVO_DUMP}" 2>/dev/null || wc -c < "${ARQUIVO_DUMP}")
NOME_ARQUIVO=$(basename "${ARQUIVO_DUMP}")

echo "[INFO] Iniciando verificação de integridade do backup..."
CHECKSUM_ATUAL=$(sha256sum "${ARQUIVO_DUMP}" | cut -d ' ' -f 1)

ARQUIVO_SHA256="${ARQUIVO_DUMP}.sha256"
if [ -f "${ARQUIVO_SHA256}" ]; then
    CHECKSUM_ESPERADO=$(cut -d ' ' -f 1 < "${ARQUIVO_SHA256}")
    if [ "${CHECKSUM_ATUAL}" != "${CHECKSUM_ESPERADO}" ]; then
        echo "[ERRO] Divergência de integridade SHA-256 detectada!" >&2
        echo "       Esperado: ${CHECKSUM_ESPERADO}" >&2
        echo "       Calculado: ${CHECKSUM_ATUAL}" >&2
        exit 1
    fi
    echo "[INFO] Integridade criptográfica SHA-256 validada com sucesso."
else
    echo "[ALERTA] Arquivo .sha256 de validação ausente. Prosseguindo com checksum atual: ${CHECKSUM_ATUAL}"
fi

echo "[INFO] Restaurando base '${PGDATABASE}' a partir de '${ARQUIVO_DUMP}'..."

if ! pg_restore \
    --host="${PGHOST}" \
    --port="${PGPORT}" \
    --username="${PGUSER}" \
    --dbname="${PGDATABASE}" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    --verbose \
    "${ARQUIVO_DUMP}"; then

    HORA_FALHA=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[ERRO] Falha durante o processo de restauração (pg_restore)." >&2

    psql \
        --host="${PGHOST}" \
        --port="${PGPORT}" \
        --username="${PGUSER}" \
        --dbname="${PGDATABASE}" \
        --no-psqlrc \
        --command="CALL sc_auditoria.sp_registrar_evento_backup('RESTORE', 'FALHA', '${PGDATABASE}', '${NOME_ARQUIVO}', ${TAMANHO_BYTES}, '${CHECKSUM_ATUAL}', '${HORA_INICIO}'::timestamptz, '${HORA_FALHA}'::timestamptz, 'Falha na execução do pg_restore');" || true

    exit 1
fi

HORA_FIM=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

echo "[INFO] Restauração executada com sucesso. Registrando no catálogo de governança..."

psql \
    --host="${PGHOST}" \
    --port="${PGPORT}" \
    --username="${PGUSER}" \
    --dbname="${PGDATABASE}" \
    --no-psqlrc \
    --command="CALL sc_auditoria.sp_registrar_evento_backup('RESTORE', 'SUCESSO', '${PGDATABASE}', '${NOME_ARQUIVO}', ${TAMANHO_BYTES}, '${CHECKSUM_ATUAL}', '${HORA_INICIO}'::timestamptz, '${HORA_FIM}'::timestamptz, NULL);" || echo "[ALERTA] Não foi possível persistir metadados em sc_auditoria.tb_historico_backup."

echo "[INFO] Revalidando contagem de linhas das tabelas restauradas:"
psql \
    --host="${PGHOST}" \
    --port="${PGPORT}" \
    --username="${PGUSER}" \
    --dbname="${PGDATABASE}" \
    --no-psqlrc \
    --command="SELECT * FROM sc_auditoria.fn_contagem_linhas_tabelas();" || true

echo "[INFO] Processo de restauração e auditoria volumétrica finalizado."
