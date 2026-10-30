// ==============================================================================
// EFFICIENTIA - TEARDOWN TOTAL DO BANCO EM GRAFO (NEO4J ROLLBACK)
// ==============================================================================
// 1. Remove todos os nós e relacionamentos do grafo
MATCH (n)
DETACH DELETE n;

// 2. Remove índices secundários
DROP INDEX idx_viagem_data IF EXISTS;
DROP INDEX idx_viagem_status IF EXISTS;
DROP INDEX idx_fazenda_uf IF EXISTS;

// 3. Remove restrições de unicidade
DROP CONSTRAINT c_fazenda_id IF EXISTS;
DROP CONSTRAINT c_pecuarista_cpf IF EXISTS;
DROP CONSTRAINT c_motorista_cnh IF EXISTS;
DROP CONSTRAINT c_veiculo_placa IF EXISTS;
DROP CONSTRAINT c_viagem_gta IF EXISTS;
DROP CONSTRAINT c_frigorifico_nome IF EXISTS;
