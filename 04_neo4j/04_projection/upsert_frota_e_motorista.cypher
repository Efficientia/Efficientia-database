// ==============================================================================
// EFFICIENTIA - PROJEÇÃO INCREMENTAL DE CONDUTOR E FROTA LOGÍSTICA
// ==============================================================================
// Projeta motoristas e veículos a partir de eventos do Outbox para o grafo.
// Parâmetros esperados:
//   $motorista_id, $motorista_nome, $motorista_cnh, $motorista_categoria
//   $cavalo_placa, $cavalo_modelo
//   $carreta_placa, $carreta_modelo, $carreta_capacidade
// ==============================================================================

// 1. Projeção do Motorista
MERGE (m:Motorista {cnh: $motorista_cnh})
ON CREATE SET
    m.id = $motorista_id,
    m.nome = $motorista_nome,
    m.categoria = $motorista_categoria,
    m.criado_em = datetime()
ON MATCH SET
    m.nome = $motorista_nome,
    m.categoria = $motorista_categoria,
    m.atualizado_em = datetime();

// 2. Projeção do Cavalo Mecânico (Caminhão Trator)
MERGE (c:Veiculo {placa: $cavalo_placa})
ON CREATE SET
    c.tipo = "cavalo_trator",
    c.modelo = $cavalo_modelo,
    c.criado_em = datetime()
ON MATCH SET
    c.modelo = $cavalo_modelo,
    c.atualizado_em = datetime();

// 3. Projeção da Carreta Boiadeira
MERGE (g:Veiculo {placa: $carreta_placa})
ON CREATE SET
    g.tipo = "carreta_gaiola",
    g.modelo = $carreta_modelo,
    g.capacidade_cabecas = toInteger($carreta_capacidade),
    g.criado_em = datetime()
ON MATCH SET
    g.capacidade_cabecas = toInteger($carreta_capacidade),
    g.atualizado_em = datetime();
