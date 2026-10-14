// ==============================================================================
// EFFICIENTIA - MODELAGEM EM GRAFO (NEO4J)
// 02. CARGA DE DADOS DE TESTE (CENÁRIO LOGÍSTICO E VETOR EPIDEMIOLÓGICO)
// ==============================================================================

// 1. Criação das Unidades Frigoríficas (Destinos)
MERGE (uf1:UnidadeFrigorifica {id: "uf-01", nome: "Frigorífico JBS Lins", municipio: "Lins", uf: "SP", capacidade_diaria: 1200})
MERGE (uf2:UnidadeFrigorifica {id: "uf-02", nome: "Frigorífico JBS Andradina", municipio: "Andradina", uf: "SP", capacidade_diaria: 900});

// 2. Criação dos Pecuaristas e Fazendas (Origens)
MERGE (p1:Pecuarista {id: "pec-01", nome: "João da Silva", cpf: "11122233344"})
MERGE (f1:Fazenda {id: "faz-01", nome: "Fazenda Esperança", municipio: "Lins", uf: "SP", area_hectares: 1500})
MERGE (p1)-[:PROPRIETARIO_DE]->(f1);

MERGE (p2:Pecuarista {id: "pec-02", nome: "Carlos Alberto Silveira", cpf: "22233344455"})
MERGE (f2:Fazenda {id: "faz-02", nome: "Fazenda Santa Maria", municipio: "Araçatuba", uf: "SP", area_hectares: 2800})
MERGE (p2)-[:PROPRIETARIO_DE]->(f2);

MERGE (p3:Pecuarista {id: "pec-03", nome: "Marcos Vinícius de Paula", cpf: "33344455566"})
MERGE (f3:Fazenda {id: "faz-03", nome: "Fazenda São José", municipio: "Andradina", uf: "SP", area_hectares: 950})
MERGE (p3)-[:PROPRIETARIO_DE]->(f3);

MERGE (p4:Pecuarista {id: "pec-04", nome: "Antônio Fagundes", cpf: "44455566677"})
MERGE (f4:Fazenda {id: "faz-04", nome: "Fazenda Boi Gordo", municipio: "Três Lagoas", uf: "MS", area_hectares: 4200})
MERGE (p4)-[:PROPRIETARIO_DE]->(f4);

// 3. Criação dos Condutores (Motoristas)
MERGE (m1:Motorista {id: "mot-01", nome: "Sebastião Moreira", cnh: "01928374651", categoria: "E"})
MERGE (m2:Motorista {id: "mot-02", nome: "Antônio Pereira", cnh: "09876543210", categoria: "E"})
MERGE (m3:Motorista {id: "mot-03", nome: "Ronaldo Nazário", cnh: "05544332211", categoria: "E"});

// 4. Criação da Frota de Veículos (Cavalos Mecânicos e Carretas Gaiola Boiadeira)
MERGE (c1:Veiculo {placa: "BRA2E19", modelo: "Scania R450", tipo: "cavalo_trator"})
MERGE (c2:Veiculo {placa: "MER1A22", modelo: "Volvo FH540", tipo: "cavalo_trator"})

MERGE (g1:Veiculo {placa: "GAI9X88", modelo: "Randon 3 Eixos Boiadeira", tipo: "carreta_gaiola", capacidade_cabecas: 50})
MERGE (g2:Veiculo {placa: "GAI4T10", modelo: "Noma 2 Eixos Boiadeira", tipo: "carreta_gaiola", capacidade_cabecas: 40});

// 5. Criação das Viagens e Conexões Logísticas

// VIAGEM 1: Origem do foco infeccioso na Fazenda Esperança
CREATE (v1:Viagem {
    id: "viag-01",
    numero_gta: "GTA-SP-00101",
    data_embarque: datetime("2026-10-01T08:00:00Z"),
    status: "aprovado",
    total_animais: 50,
    qtd_morto: 2,
    laudo_sanitario_suspeito: true
})
CREATE (v1)-[:PARTIU_DE]->(f1)
CREATE (v1)-[:DESTINADA_A]->(uf1)
CREATE (v1)-[:CONDUZIDA_POR]->(m1)
CREATE (v1)-[:UTILIZOU_VEICULO {compartimento: "trator"}]->(c1)
CREATE (v1)-[:UTILIZOU_VEICULO {compartimento: "gaiola"}]->(g1);

// VIAGEM 2: Contaminação indireta no dia seguinte pelo compartilhamento da carreta GAI9X88
CREATE (v2:Viagem {
    id: "viag-02",
    numero_gta: "GTA-SP-00102",
    data_embarque: datetime("2026-10-02T09:30:00Z"),
    status: "aprovado",
    total_animais: 48,
    qtd_morto: 0,
    laudo_sanitario_suspeito: false
})
CREATE (v2)-[:PARTIU_DE]->(f2)
CREATE (v2)-[:DESTINADA_A]->(uf1)
CREATE (v2)-[:CONDUZIDA_POR]->(m1)
CREATE (v2)-[:UTILIZOU_VEICULO {compartimento: "trator"}]->(c1)
CREATE (v2)-[:UTILIZOU_VEICULO {compartimento: "gaiola"}]->(g1);

// VIAGEM 3: O mesmo cavalo e carreta viajam para o Mato Grosso do Sul (propagação interestadual)
CREATE (v3:Viagem {
    id: "viag-03",
    numero_gta: "GTA-MS-00201",
    data_embarque: datetime("2026-10-03T11:00:00Z"),
    status: "aprovado",
    total_animais: 50,
    qtd_morto: 1,
    laudo_sanitario_suspeito: false
})
CREATE (v3)-[:PARTIU_DE]->(f4)
CREATE (v3)-[:DESTINADA_A]->(uf2)
CREATE (v3)-[:CONDUZIDA_POR]->(m2)
CREATE (v3)-[:UTILIZOU_VEICULO {compartimento: "trator"}]->(c1)
CREATE (v3)-[:UTILIZOU_VEICULO {compartimento: "gaiola"}]->(g1);

// VIAGEM 4: Rota Limpa / Controle Sanitário (Não compartilhou equipamento contaminado)
CREATE (v4:Viagem {
    id: "viag-04",
    numero_gta: "GTA-SP-00103",
    data_embarque: datetime("2026-10-04T07:15:00Z"),
    status: "aprovado",
    total_animais: 40,
    qtd_morto: 0,
    laudo_sanitario_suspeito: false
})
CREATE (v4)-[:PARTIU_DE]->(f3)
CREATE (v4)-[:DESTINADA_A]->(uf2)
CREATE (v4)-[:CONDUZIDA_POR]->(m3)
CREATE (v4)-[:UTILIZOU_VEICULO {compartimento: "trator"}]->(c2)
CREATE (v4)-[:UTILIZOU_VEICULO {compartimento: "gaiola"}]->(g2);

// VIAGEM 5: Transbordo / Troca de implemento (A carreta contaminada GAI9X88 acoplou no cavalo C2)
CREATE (v5:Viagem {
    id: "viag-05",
    numero_gta: "GTA-SP-00104",
    data_embarque: datetime("2026-10-05T14:00:00Z"),
    status: "aprovado",
    total_animais: 50,
    qtd_morto: 0,
    laudo_sanitario_suspeito: false
})
CREATE (v5)-[:PARTIU_DE]->(f2)
CREATE (v5)-[:DESTINADA_A]->(uf2)
CREATE (v5)-[:CONDUZIDA_POR]->(m3)
CREATE (v5)-[:UTILIZOU_VEICULO {compartimento: "trator"}]->(c2)
CREATE (v5)-[:UTILIZOU_VEICULO {compartimento: "gaiola"}]->(g1);
