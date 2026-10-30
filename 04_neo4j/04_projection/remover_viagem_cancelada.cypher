// ==============================================================================
// EFFICIENTIA - REVERSÃO / EXCLUSÃO DE VIAGEM NO GRAFO
// ==============================================================================
// Utilizado quando um evento de cancelamento ou estorno cirúrgico no PostgreSQL
// exige a desmaterialização da viagem no grafo Neo4j.
// Parâmetro: $numero_gta
// ==============================================================================

MATCH (vg:Viagem {numero_gta: $numero_gta})
DETACH DELETE vg;
