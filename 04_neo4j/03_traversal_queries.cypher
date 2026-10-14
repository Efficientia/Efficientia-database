// ==============================================================================
// EFFICIENTIA - MODELAGEM EM GRAFO (NEO4J)
// 03. CONSULTAS DE NEGÓCIO UTILIZANDO TRAVERSAL
// ==============================================================================

// ==============================================================================
// CONSULTA 1 (PRINCIPAL): RASTREAMENTO EPIDEMIOLÓGICO E CONTÁGIO CRUZADO
// Pergunta de Negócio:
// "A partir de um lote com suspeita sanitária confirmado na Fazenda Esperança,
// quais outras fazendas, veículos e frigoríficos foram expostos por contato indireto
// devido ao compartilhamento de veículos em viagens subsequentes?"
// ==============================================================================
MATCH path = (origem:Fazenda {nome: "Fazenda Esperança"})
             <-[:PARTIU_DE]-(v_origem:Viagem)
             -[:UTILIZOU_VEICULO]->(vetor:Veiculo)
             <-[:UTILIZOU_VEICULO]-(v_exposta:Viagem)
             -[:PARTIU_DE|DESTINADA_A]->(entidade_em_risco)
WHERE v_exposta.data_embarque >= v_origem.data_embarque
  AND v_exposta.numero_gta <> v_origem.numero_gta
  AND entidade_em_risco.nome <> origem.nome
RETURN DISTINCT
    origem.nome                  AS foco_infeccioso,
    v_origem.numero_gta          AS gta_origem,
    vetor.placa                  AS veiculo_vetor,
    vetor.tipo                   AS tipo_implemento,
    v_exposta.numero_gta         AS gta_contaminada,
    v_exposta.data_embarque      AS data_contato,
    labels(entidade_em_risco)[0] AS tipo_entidade_exposta,
    entidade_em_risco.nome       AS local_para_quarentena,
    entidade_em_risco.municipio  AS municipio_em_risco
ORDER BY v_exposta.data_embarque ASC;

// EXPLICAÇÃO TÉCNICA DO TRAVERSAL 1:
// O motor do Neo4j parte do nó 'Fazenda Esperança', navega na aresta inversa (:PARTIU_DE),
// atinge a viagem inicial, atravessa (:UTILIZOU_VEICULO) para encontrar o implemento (carreta GAI9X88),
// e faz o salto para trás alcançando todas as viagens que utilizaram aquele mesmo implemento no futuro,
// finalizando nos nós de outras Fazendas e Frigoríficos.


// ==============================================================================
// CONSULTA 2: CAMINHO MAIS CURTO DE PROPAGAÇÃO SANITÁRIA (SHORTEST PATH)
// Pergunta de Negócio:
// "Em quantos saltos na malha logística a suspeita sanitária da Fazenda Esperança
// atingiu o Frigorífico JBS Andradina, e quais implementos intermediários intermediaram o trajeto?"
// ==============================================================================
MATCH (origem:Fazenda {nome: "Fazenda Esperança"}),
      (destino:UnidadeFrigorifica {nome: "Frigorífico JBS Andradina"})
MATCH path = shortestPath((origem)-[*..8]-(destino))
RETURN path,
       length(path) AS total_saltos,
       [n IN nodes(path) | coalesce(n.nome, n.placa, n.numero_gta)] AS sequencia_da_cadeia;

// EXPLICAÇÃO TÉCNICA DO TRAVERSAL 2:
// O algoritmo 'shortestPath' percorre a malha em busca da menor cadeia de nós que conecta
// a fazenda infectada ao frigorífico em outra comarca, revelando que a contaminação cruzou
// fronteiras estaduais graças à troca de implemento (carreta acoplada a outro cavalo mecânico).


// ==============================================================================
// CONSULTA 3: ANÁLISE DE HUBS LOGÍSTICOS E GRAU DE CENTRALIDADE
// Pergunta de Negócio:
// "Quais implementos de transporte (cavalos ou carretas) conectam o maior número de
// fazendas e frigoríficos distintos, sendo classificados como super-disseminadores em caso de surto?"
// ==============================================================================
MATCH (veic:Veiculo)<-[:UTILIZOU_VEICULO]-(v:Viagem)
OPTIONAL MATCH (v)-[:PARTIU_DE]->(f:Fazenda)
OPTIONAL MATCH (v)-[:DESTINADA_A]->(uf:UnidadeFrigorifica)
WITH veic,
     count(DISTINCT f) AS fazendas_atendidas,
     count(DISTINCT uf) AS frigorificos_atendidos,
     count(DISTINCT v) AS total_viagens
RETURN
    veic.placa AS veiculo,
    veic.tipo AS tipo_veiculo,
    veic.modelo AS modelo,
    fazendas_atendidas,
    frigorificos_atendidos,
    total_viagens,
    (fazendas_atendidas + frigorificos_atendidos) AS score_centralidade_risco
ORDER BY score_centralidade_risco DESC, total_viagens DESC;
