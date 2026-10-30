// ==============================================================================
// EFFICIENTIA - PROJEÇÃO INCREMENTAL DE VIAGEM APROVADA E TOPOLOGIA DE ROTA
// ==============================================================================
// Materializa no grafo o nó da Viagem e conecta a topologia logística:
//   Origem (Fazenda) -> Viagem -> Destino (Frigorífico)
//   Viagem -> Condutor (Motorista)
//   Viagem -> Equipamentos (Cavalo e Carreta)
// Parâmetros esperados:
//   $viagem_id, $numero_gta, $data_embarque_iso, $status, $total_animais, $qtd_morto
//   $laudo_sanitario_suspeito, $fazenda_id, $unidade_id, $motorista_cnh
//   $cavalo_placa, $carreta_placa
// ==============================================================================

// 1. Cria ou atualiza o nó da Viagem
MERGE (vg:Viagem {numero_gta: $numero_gta})
ON CREATE SET
    vg.id = $viagem_id,
    vg.data_embarque = datetime($data_embarque_iso),
    vg.status = $status,
    vg.total_animais = toInteger($total_animais),
    vg.qtd_morto = toInteger($qtd_morto),
    vg.laudo_sanitario_suspeito = toBoolean($laudo_sanitario_suspeito),
    vg.projetado_em = datetime()
ON MATCH SET
    vg.status = $status,
    vg.total_animais = toInteger($total_animais),
    vg.qtd_morto = toInteger($qtd_morto),
    vg.laudo_sanitario_suspeito = toBoolean($laudo_sanitario_suspeito),
    vg.atualizado_em = datetime();

// 2. Conexão com Origem (Fazenda)
WITH vg
MATCH (f:Fazenda {id: $fazenda_id})
MERGE (vg)-[:ORIGEM]->(f);

// 3. Conexão com Destino (Unidade Frigorífica)
WITH vg
MATCH (uf:UnidadeFrigorifica {id: $unidade_id})
MERGE (vg)-[:DESTINO]->(uf);

// 4. Conexão com Motorista Responsável
WITH vg
MATCH (m:Motorista {cnh: $motorista_cnh})
MERGE (vg)-[:CONDUZIDA_POR]->(m);

// 5. Conexão com os Veículos Utilizados
WITH vg
MATCH (c:Veiculo {placa: $cavalo_placa})
MERGE (vg)-[:UTILIZOU_VEICULO]->(c);

WITH vg
MATCH (g:Veiculo {placa: $carreta_placa})
MERGE (vg)-[:UTILIZOU_VEICULO]->(g);
