// ==============================================================================
// EFFICIENTIA - PROJEÇÃO INCREMENTAL DE PROPRIEDADE RURAL E FRIGORÍFICO
// ==============================================================================
// Projeta eventos do Transactional Outbox (PostgreSQL) para nós no Grafo Neo4j.
// Parâmetros esperados no payload:
//   $fazenda_id, $fazenda_nome, $fazenda_municipio, $fazenda_uf, $fazenda_area
//   $pecuarista_id, $pecuarista_nome, $pecuarista_cpf
//   $unidade_id, $unidade_nome, $unidade_municipio, $unidade_uf, $unidade_capacidade
// ==============================================================================

// 1. Projeção de Pecuarista e Fazenda (Origem)
MERGE (p:Pecuarista {cpf: $pecuarista_cpf})
ON CREATE SET
    p.id = $pecuarista_id,
    p.nome = $pecuarista_nome,
    p.criado_em = datetime()
ON MATCH SET
    p.nome = $pecuarista_nome,
    p.atualizado_em = datetime();

MERGE (f:Fazenda {id: $fazenda_id})
ON CREATE SET
    f.nome = $fazenda_nome,
    f.municipio = $fazenda_municipio,
    f.uf = $fazenda_uf,
    f.area_hectares = toInteger($fazenda_area),
    f.criado_em = datetime()
ON MATCH SET
    f.nome = $fazenda_nome,
    f.municipio = $fazenda_municipio,
    f.uf = $fazenda_uf,
    f.atualizado_em = datetime();

MERGE (p)-[:PROPRIETARIO_DE]->(f);

// 2. Projeção de Unidade Frigorífica (Destino)
MERGE (uf:UnidadeFrigorifica {id: $unidade_id})
ON CREATE SET
    uf.nome = $unidade_nome,
    uf.municipio = $unidade_municipio,
    uf.uf = $unidade_uf,
    uf.capacidade_diaria = toInteger($unidade_capacidade),
    uf.criado_em = datetime()
ON MATCH SET
    uf.nome = $unidade_nome,
    uf.municipio = $unidade_municipio,
    uf.uf = $unidade_uf,
    uf.atualizado_em = datetime();
