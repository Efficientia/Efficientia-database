#!/usr/bin/env bash
# ==============================================================================
# PROJETO EFFICIENTIA - RUNNER DE TESTES AUTOMATIZADOS DO NEO4J
# ==============================================================================

set -euo pipefail

NEO4J_URI="${NEO4J_URI:-neo4j://localhost:7687}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-efficientia123}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "=============================================================================="
echo "Iniciando bateria de validação do banco de grafos Neo4j"
echo "Alvo: ${NEO4J_USER}@${NEO4J_URI}"
echo "=============================================================================="

CYPHER_FILES=(
    "${BASE_DIR}/01_schema_constraints.cypher"
    "${BASE_DIR}/02_seed_data.cypher"
    "${BASE_DIR}/03_traversal_queries.cypher"
)

for file in "${CYPHER_FILES[@]}"; do
    echo ""
    echo "[TESTE NEO4J] Executando $(basename "${file}")..."
    cypher-shell \
        --address "${NEO4J_URI}" \
        --user "${NEO4J_USER}" \
        --password "${NEO4J_PASSWORD}" \
        --file "${file}"
    echo "[SUCESSO] $(basename "${file}") executado com êxito."
done

echo ""
echo "=============================================================================="
echo "Todos os testes do Neo4j foram concluídos com sucesso!"
echo "=============================================================================="
