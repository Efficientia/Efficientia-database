// ==============================================================================
// EFFICIENTIA - MODELAGEM EM GRAFO (NEO4J)
// 01. CONSTRAINTS DE UNICIDADE E ÍNDICES DE PERFORMANCE
// ==============================================================================

// 1. Constraints de Unicidade (Garantem integridade e criam índices automáticos)
CREATE CONSTRAINT c_fazenda_id IF NOT EXISTS
FOR (f:Fazenda) REQUIRE f.id IS UNIQUE;

CREATE CONSTRAINT c_pecuarista_cpf IF NOT EXISTS
FOR (p:Pecuarista) REQUIRE p.cpf IS UNIQUE;

CREATE CONSTRAINT c_motorista_cnh IF NOT EXISTS
FOR (m:Motorista) REQUIRE m.cnh IS UNIQUE;

CREATE CONSTRAINT c_veiculo_placa IF NOT EXISTS
FOR (v:Veiculo) REQUIRE v.placa IS UNIQUE;

CREATE CONSTRAINT c_viagem_gta IF NOT EXISTS
FOR (vg:Viagem) REQUIRE vg.numero_gta IS UNIQUE;

CREATE CONSTRAINT c_frigorifico_nome IF NOT EXISTS
FOR (uf:UnidadeFrigorifica) REQUIRE uf.nome IS UNIQUE;

// 2. Índices de Busca para Otimização de Filtros e Traversals
CREATE INDEX idx_viagem_data IF NOT EXISTS
FOR (vg:Viagem) ON (vg.data_embarque);

CREATE INDEX idx_viagem_status IF NOT EXISTS
FOR (vg:Viagem) ON (vg.status);

CREATE INDEX idx_fazenda_uf IF NOT EXISTS
FOR (f:Fazenda) ON (f.uf);
