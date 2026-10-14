/**
 * ==============================================================================
 * PROJETO EFFICIENTIA - BANCO DE DADOS CONVERSACIONAL (MONGODB)
 * Sprint 08 - MD-50 / EFFICIENTI-306
 * Arquivo: 04_conversational_queries.js
 * Descrição: Consultas operacionais e pipelines de agregação para suporte
 *            às interações da IA, observabilidade e inteligência de negócios.
 * ==============================================================================
 */

const dbName = "efficientia_ai";
const currentDb = db.getSiblingDB ? db.getSiblingDB(dbName) : db;

print(`[MongoDB] Executando consultas de demonstração no banco: ${dbName}...\n`);

// ==============================================================================
// CONSULTA 1: Recuperação de Contexto do Chat para o Modelo LLM
// Objetivo: Carregar as mensagens cronológicas de uma sessão para montar o prompt.
// Performance: Utiliza o índice composto idx_messages_thread_timestamp_asc.
// ==============================================================================
print("--- [CONSULTA 1] Histórico Cronológico da Sessão 'eficientia_sessao_001' (Contexto LLM) ---");
const contextMessages = currentDb.messages.find(
  { thread_id: "eficientia_sessao_001" },
  { _id: 0, role: 1, agente_origem: 1, content: 1, timestamp: 1 }
)
.sort({ timestamp: 1 })
.toArray();

printjson(contextMessages);
print("\n" + "=".repeat(80) + "\n");

// ==============================================================================
// CONSULTA 2: Busca da Sessão Ativa do Motorista com Última Mensagem ($lookup)
// Objetivo: Quando o motorista abre o app, recuperar sua sessão ativa e o último status.
// ==============================================================================
print("--- [CONSULTA 2] Sessão Ativa do Motorista '123.456.789-00' com Última Interação ---");
const activeSessionWithLastMsg = currentDb.threads.aggregate([
  {
    $match: {
      usuario_id: "123.456.789-00",
      status: "ativa"
    }
  },
  {
    $lookup: {
      from: "messages",
      let: { tId: "$thread_id" },
      pipeline: [
        { $match: { $expr: { $eq: ["$thread_id", "$$tId"] } } },
        { $sort: { timestamp: -1 } },
        { $limit: 1 },
        { $project: { _id: 0, role: 1, content: 1, timestamp: 1 } }
      ],
      as: "ultima_mensagem"
    }
  },
  {
    $unwind: {
      path: "$ultima_mensagem",
      preserveNullAndEmptyArrays: true
    }
  }
]).toArray();

printjson(activeSessionWithLastMsg);
print("\n" + "=".repeat(80) + "\n");

// ==============================================================================
// CONSULTA 3: Observabilidade da IA - Custo de Tokens e Latência Média (FinOps/SLO)
// Objetivo: Medir o consumo total de tokens e a latência de resposta do orquestrador.
// ==============================================================================
print("--- [CONSULTA 3] Métricas de Observabilidade da IA (Tokens e Latência) ---");
const aiObservabilityMetrics = currentDb.messages.aggregate([
  {
    $match: {
      role: "assistant",
      "metadata.tokens_used": { $exists: true }
    }
  },
  {
    $group: {
      _id: "$agente_origem",
      total_respostas: { $sum: 1 },
      total_tokens_consumidos: { $sum: "$metadata.tokens_used" },
      tokens_medio_por_resposta: { $avg: "$metadata.tokens_used" },
      latencia_media_ms: { $avg: "$metadata.latency_ms" },
      latencia_maxima_ms: { $max: "$metadata.latency_ms" }
    }
  },
  {
    $project: {
      _id: 0,
      agente: "$_id",
      total_respostas: 1,
      total_tokens_consumidos: 1,
      tokens_medio_por_resposta: { $round: ["$tokens_medio_por_resposta", 1] },
      latencia_media_ms: { $round: ["$latencia_media_ms", 1] },
      latencia_maxima_ms: 1
    }
  }
]).toArray();

printjson(aiObservabilityMetrics);
print("\n" + "=".repeat(80) + "\n");

// ==============================================================================
// CONSULTA 4: Inteligência Operacional - Dúvidas e Intenções mais Frequentes
// Objetivo: Identificar gargalos operacionais e tópicos que geram mais dúvidas na frota.
// ==============================================================================
print("--- [CONSULTA 4] Ranking de Dúvidas e Intenções dos Motoristas ---");
const topIntents = currentDb.messages.aggregate([
  {
    $match: {
      "json_orquestrador.intencao": { $exists: true }
    }
  },
  {
    $group: {
      _id: {
        dominio: "$json_orquestrador.dominio",
        intencao: "$json_orquestrador.intencao"
      },
      quantidade_perguntas: { $sum: 1 },
      exemplo_resposta: { $first: "$json_orquestrador.resposta" }
    }
  },
  {
    $sort: { quantidade_perguntas: -1 }
  },
  {
    $project: {
      _id: 0,
      dominio: "$_id.dominio",
      intencao: "$_id.intencao",
      quantidade_perguntas: 1,
      exemplo_resposta: 1
    }
  }
]).toArray();

printjson(topIntents);
print("\n[MongoDB] Execução de todas as consultas finalizada.");
