/**
 * ==============================================================================
 * PROJETO EFFICIENTIA - BANCO DE DADOS CONVERSACIONAL (MONGODB)
 * Sprint 08 - MD-50 / EFFICIENTI-306
 * Arquivo: 02_indexes.js
 * Descrição: Criação de índices para otimização de consultas em tempo real,
 *            recuperação de contexto conversacional e observabilidade da IA.
 * ==============================================================================
 */

const dbName = "efficientia_ai";
const currentDb = db.getSiblingDB ? db.getSiblingDB(dbName) : db;

print(`[MongoDB] Configurando índices para otimização de performance no banco: ${dbName}...`);

// ==============================================================================
// 1. ÍNDICES NA COLEÇÃO: threads
// ==============================================================================

// Garantir unicidade do identificador de sessão
currentDb.threads.createIndex(
  { thread_id: 1 },
  { unique: true, name: "idx_threads_thread_id_unique" }
);
print(" - Criado: idx_threads_thread_id_unique (Unicidade de sessão)");

// Busca rápida da sessão ativa do motorista ao abrir o aplicativo
currentDb.threads.createIndex(
  { usuario_id: 1, status: 1 },
  { name: "idx_threads_usuario_status" }
);
print(" - Criado: idx_threads_usuario_status (Busca de sessões por motorista e status)");

// Consulta de atendimentos vinculados a uma placa de carreta/veículo
currentDb.threads.createIndex(
  { placa_veiculo: 1 },
  { name: "idx_threads_placa_veiculo" }
);
print(" - Criado: idx_threads_placa_veiculo (Rastreamento por veículo)");

// Listagem de sessões recentes para o painel de suporte/gestão de frota
currentDb.threads.createIndex(
  { atualizado_em: -1 },
  { name: "idx_threads_atualizado_em_desc" }
);
print(" - Criado: idx_threads_atualizado_em_desc (Ordenação de sessões recentes)");

// ==============================================================================
// 2. ÍNDICES NA COLEÇÃO: messages
// ==============================================================================

// O ÍNDICE MAIS CRÍTICO: Recuperação cronológica do histórico para contexto do LLM
// Evita qualquer operação de Sort em memória no servidor MongoDB.
currentDb.messages.createIndex(
  { thread_id: 1, timestamp: 1 },
  { name: "idx_messages_thread_timestamp_asc" }
);
print(" - Criado: idx_messages_thread_timestamp_asc (Ordenação cronológica do chat)");

// Observabilidade, APM e rastreamento distribuído por trace_id
currentDb.messages.createIndex(
  { "metadata.trace_id": 1 },
  { name: "idx_messages_metadata_trace_id" }
);
print(" - Criado: idx_messages_metadata_trace_id (Auditoria e rastreamento APM)");

// Análise estatística de intenções e domínios classificados pelo orquestrador
currentDb.messages.createIndex(
  { "json_orquestrador.dominio": 1, "json_orquestrador.intencao": 1 },
  { name: "idx_messages_orquestrador_dominio_intencao" }
);
print(" - Criado: idx_messages_orquestrador_dominio_intencao (Agrupamento por intenção)");

print("\n[MongoDB] Todos os índices foram criados com sucesso.");
