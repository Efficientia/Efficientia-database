#!/usr/bin/env bash
# ==============================================================================
# PROJETO EFFICIENTIA - SCRIPT DE BACKUP FÍSICO / LÓGICO COMPACTADO
# ==============================================================================
# Executa cópia de segurança em formato customizado do PostgreSQL (pg_dump -Fc),
# calcula checksum SHA-256 para integridade e registra metadados no histórico
# de governança (sc_auditoria.tb_historico_backup).
# ==============================================================================

set -euo pipefail

# Parâmetros de conexão com valores padrão
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-efficientia}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
ARQUIVO_DUMP="efficientia_backup_${TIMESTAMP}.dump"
CAMINHO_DUMP="${BACKUP_DIR}/${ARQUIVO_DUMP}"
HORA_INICIO=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

mkdir -p "${BACKUP_DIR}"

echo "[INFO] Iniciando rotina de backup para o banco '${PGDATABASE}' em ${HORA_INICIO}..."

if ! pg_dump \
    --host="${PGHOST}" \
    --port="${PGPORT}" \
    --username="${PGUSER}" \
    --format=custom \
    --compress=9 \
    --blobs \
    --verbose \
    --file="${CAMINHO_DUMP}" \
    "${PGDATABASE}"; then
    
    HORA_FALHA=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[ERRO] Falha crítica durante a execução do pg_dump." >&2
    
    # Tentativa de registrar falha no banco caso conexão persista
    psql \
        --host="${PGHOST}" \
        --port="${PGPORT}" \
        --username="${PGUSER}" \
        --dbname="${PGDATABASE}" \
        --no-psqlrc \
        --command="CALL sc_auditoria.sp_registrar_evento_backup('BACKUP', 'FALHA', '${PGDATABASE}', '${ARQUIVO_DUMP}', 0, NULL, '${HORA_INICIO}'::timestamptz, '${HORA_FALHA}'::timestamptz, 'Falha de execução no comando pg_dump');" || true

    exit 1
fi

HORA_FIM=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TAMANHO_BYTES=$(stat -c%s "${CAMINHO_DUMP}" 2>/dev/null || stat -f%z "${CAMINHO_DUMP}" 2>/dev/null || wc -c < "${CAMINHO_DUMP}")
CHECKSUM_SHA256=$(sha256sum "${CAMINHO_DUMP}" | cut -d ' ' -f 1)

echo "${CHECKSUM_SHA256}  ${ARQUIVO_DUMP}" > "${CAMINHO_DUMP}.sha256"

echo "[INFO] Backup concluído com sucesso."
echo "       Arquivo:  ${CAMINHO_DUMP}"
echo "       Tamanho:  ${TAMANHO_BYTES} bytes"
echo "       SHA-256:  ${CHECKSUM_SHA256}"

# Registro no histórico de auditoria do banco
psql \
    --host="${PGHOST}" \
    --port="${PGPORT}" \
    --username="${PGUSER}" \
    --dbname="${PGDATABASE}" \
    --no-psqlrc \
    --command="CALL sc_auditoria.sp_registrar_evento_backup('BACKUP', 'SUCESSO', '${PGDATABASE}', '${ARQUIVO_DUMP}', ${TAMANHO_BYTES}, '${CHECKSUM_SHA256}', '${HORA_INICIO}'::timestamptz, '${HORA_FIM}'::timestamptz, NULL);" || echo "[ALERTA] Não foi possível persistir metadados em sc_auditoria.tb_historico_backup."

echo "[INFO] Rotina de backup finalizada."
