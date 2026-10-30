#!/usr/bin/env bash
# ==============================================================================
# PROJETO EFFICIENTIA - RUNNER DE TESTES AUTOMATIZADOS DO POSTGRESQL
# ==============================================================================

set -euo pipefail

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-efficientia}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=============================================================================="
echo "Iniciando bateria de testes automatizados do banco de dados relacional"
echo "Alvo: ${PGUSER}@${PGHOST}:${PGPORT}/${PGDATABASE}"
echo "=============================================================================="

SUITES=(
    "01_test_regras_negocio_e_validacoes.sql"
    "02_test_hierarquia_recursiva.sql"
    "03_test_auditoria_dau_e_recuperacao.sql"
)

for suite in "${SUITES[@]}"; do
    caminho="${SCRIPT_DIR}/${suite}"
    echo ""
    echo "[TESTE] Executando: ${suite}..."
    psql \
        --host="${PGHOST}" \
        --port="${PGPORT}" \
        --username="${PGUSER}" \
        --dbname="${PGDATABASE}" \
        --no-psqlrc \
        --variable="ON_ERROR_STOP=1" \
        --file="${caminho}"
    echo "[SUCESSO] ${suite} aprovada."
done

echo ""
echo "=============================================================================="
echo "Todos os testes do PostgreSQL foram executados com êxito!"
echo "=============================================================================="
