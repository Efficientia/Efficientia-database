/**
 * ==============================================================================
 * PROJETO EFFICIENTIA - BANCO DE DADOS CONVERSACIONAL (MONGODB)
 * Sprint 08 - MD-50 / EFFICIENTI-306
 * Arquivo: 01_schema_validation.js
 * Descrição: Criação das coleções "threads" e "messages" com validação
 *            rigorosa via $jsonSchema para armazenamento de interações da IA.
 * ==============================================================================
 */

// Conectar ao banco de dados da IA
const dbName = "efficientia_ai";
const currentDb = db.getSiblingDB ? db.getSiblingDB(dbName) : db;

print(`[MongoDB] Configurando esquemas de validação no banco: ${dbName}...`);

// ==============================================================================
// 1. COLEÇÃO: threads
// Representa a sessão conversacional entre um motorista/usuário e o orquestrador.
// ==============================================================================
try {
  currentDb.threads.drop();
  print("[MongoDB] Coleção 'threads' anterior removida para reinicialização.");
} catch (e) {
  // Ignora se não existir
}

currentDb.createCollection("threads", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["thread_id", "usuario_id", "status", "criado_em", "atualizado_em"],
      properties: {
        thread_id: {
          bsonType: "string",
          description: "Identificador único da sessão conversacional (ex: eficientia_sessao_001)"
        },
        usuario_id: {
          bsonType: "string",
          description: "CPF ou identificador do usuário (chave lógica de integração com PostgreSQL sc_operacao.tb_usuario)"
        },
        placa_veiculo: {
          bsonType: "string",
          description: "Placa do veículo operacional vinculado à sessão (chave lógica com sc_operacao.tb_veiculo_base)"
        },
        status: {
          bsonType: "string",
          enum: ["ativa", "encerrada", "arquivada"],
          description: "Status do ciclo de vida da thread conversacional"
        },
        criado_em: {
          bsonType: "date",
          description: "Data e hora de abertura da thread"
        },
        atualizado_em: {
          bsonType: "date",
          description: "Data e hora do último evento ou mensagem na thread"
        }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});

print("[MongoDB] Coleção 'threads' criada com sucesso com $jsonSchema validator.");

// ==============================================================================
// 2. COLEÇÃO: messages
// Representa cada turno de mensagem (usuário, orquestrador, ferramentas e metadados).
// ==============================================================================
try {
  currentDb.messages.drop();
  print("[MongoDB] Coleção 'messages' anterior removida para reinicialização.");
} catch (e) {
  // Ignora se não existir
}

currentDb.createCollection("messages", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["thread_id", "role", "content", "timestamp"],
      properties: {
        thread_id: {
          bsonType: "string",
          description: "Identificador da thread pai (referência documental para threads.thread_id)"
        },
        role: {
          bsonType: "string",
          enum: ["user", "assistant", "system", "tool"],
          description: "Papel do remetente da mensagem na conversa"
        },
        agente_origem: {
          bsonType: "string",
          description: "Identificação do agente de IA que produziu a resposta (ex: orquestrador)"
        },
        content: {
          bsonType: "string",
          description: "Texto da mensagem exibida ao usuário ou enviada pelo usuário"
        },
        tool_calls: {
          bsonType: "array",
          description: "Chamadas de ferramentas e funções disparadas pelo LLM",
          items: {
            bsonType: "object"
          }
        },
        tool_outputs: {
          bsonType: "array",
          description: "Retornos recebidos das ferramentas acionadas",
          items: {
            bsonType: "object"
          }
        },
        json_orquestrador: {
          bsonType: "object",
          description: "Estrutura semântica gerada pelo agente orquestrador",
          properties: {
            dominio: {
              bsonType: "string",
              description: "Domínio operacional classificado (ex: motorista, telemetria, manutencao)"
            },
            intencao: {
              bsonType: "string",
              description: "Intenção identificada na dúvida/solicitação do motorista"
            },
            resposta: {
              bsonType: "string",
              description: "Texto consolidado da resposta do orquestrador"
            },
            acompanhamento: {
              bsonType: "string",
              description: "Sugestão proativa ou pergunta de continuidade para o usuário"
            }
          }
        },
        timestamp: {
          bsonType: "date",
          description: "Data e hora exata em que a mensagem foi gerada"
        },
        metadata: {
          bsonType: "object",
          description: "Métricas de telemetria e observabilidade da execução do modelo",
          properties: {
            trace_id: {
              bsonType: "string",
              description: "Identificador de rastreamento distribuído (APM/OpenTelemetry)"
            },
            tokens_used: {
              bsonType: ["int", "long", "double"],
              description: "Consumo total de tokens (prompt + completion) desta mensagem"
            },
            latency_ms: {
              bsonType: ["int", "long", "double"],
              description: "Tempo de resposta do modelo/orquestrador em milissegundos"
            }
          }
        }
      }
    }
  },
  validationLevel: "strict",
  validationAction: "error"
});

print("[MongoDB] Coleção 'messages' criada com sucesso com $jsonSchema validator.");
