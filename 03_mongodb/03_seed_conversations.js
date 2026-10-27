/**
 * ==============================================================================
 * PROJETO EFFICIENTIA - BANCO DE DADOS CONVERSACIONAL (MONGODB)
 * Arquivo: 03_seed_conversations.js
 * Descrição: Carga de dados iniciais (Seed) contendo threads de atendimento
 *            e histórico de mensagens trocadas com o Agente Orquestrador de IA.
 * ==============================================================================
 */

const dbName = "efficientia_ai";
const currentDb = db.getSiblingDB ? db.getSiblingDB(dbName) : db;

print(`[MongoDB] Iniciando carga de dados (Seed) no banco: ${dbName}...`);

// Limpar dados anteriores para permitir reexecução limpa e idempotente
currentDb.threads.deleteMany({});
currentDb.messages.deleteMany({});

// ==============================================================================
// 1. CARGA DA COLEÇÃO: threads
// ==============================================================================
const threadsData = [
  {
    thread_id: "eficientia_sessao_001",
    usuario_id: "123.456.789-00",
    placa_veiculo: "ABC-1234",
    status: "ativa",
    criado_em: new Date("2026-08-20T10:00:00.000Z"),
    atualizado_em: new Date("2026-08-20T10:05:00.000Z")
  },
  {
    thread_id: "eficientia_sessao_002",
    usuario_id: "987.654.321-11",
    placa_veiculo: "XYZ-9876",
    status: "encerrada",
    criado_em: new Date("2026-08-20T14:00:00.000Z"),
    atualizado_em: new Date("2026-08-20T14:08:00.000Z")
  }
];

const threadsResult = currentDb.threads.insertMany(threadsData);
print(`[MongoDB] ${Object.keys(threadsResult.insertedIds).length} threads inseridas com sucesso.`);

// ==============================================================================
// 2. CARGA DA COLEÇÃO: messages
// ==============================================================================
const messagesData = [
  // --- Sessão 001: Turno 1 (Dúvida sobre horário de embarque da carreta) ---
  {
    thread_id: "eficientia_sessao_001",
    role: "user",
    content: "Preciso de ajuda para preencher o horário de embarque da carreta.",
    timestamp: new Date("2026-08-20T10:01:00.000Z"),
    metadata: {
      trace_id: "uuid-da-execucao-001"
    }
  },
  {
    thread_id: "eficientia_sessao_001",
    role: "assistant",
    agente_origem: "orquestrador",
    content: "O horário de embarque é preenchido automaticamente pelo sistema quando o motorista inicia a viagem no aplicativo. Você precisa de ajuda com algum campo manual, como a quilometragem de saída?",
    tool_calls: [],
    tool_outputs: [],
    json_orquestrador: {
      dominio: "motorista",
      intencao: "esclarecer_preenchimento",
      resposta: "O horário de embarque é preenchido automaticamente pelo sistema quando o motorista inicia a viagem no aplicativo.",
      acompanhamento: "Você precisa de ajuda com algum campo manual, como a quilometragem de saída?"
    },
    timestamp: new Date("2026-08-20T10:01:05.000Z"),
    metadata: {
      trace_id: "uuid-da-execucao-001",
      tokens_used: 150,
      latency_ms: 450
    }
  },

  // --- Sessão 001: Turno 2 (Continuidade do diálogo) ---
  {
    thread_id: "eficientia_sessao_001",
    role: "user",
    content: "Sim, onde digito o odômetro inicial?",
    timestamp: new Date("2026-08-20T10:02:10.000Z"),
    metadata: {
      trace_id: "uuid-da-execucao-002"
    }
  },
  {
    thread_id: "eficientia_sessao_001",
    role: "assistant",
    agente_origem: "orquestrador",
    content: "Na tela 'Iniciar Viagem', toque no campo 'Odômetro Inicial' logo abaixo da placa da carreta. Digite o valor numérico e confirme se a foto do painel foi anexada.",
    tool_calls: [],
    tool_outputs: [],
    json_orquestrador: {
      dominio: "motorista",
      intencao: "esclarecer_preenchimento",
      resposta: "Na tela 'Iniciar Viagem', toque no campo 'Odômetro Inicial' logo abaixo da placa da carreta.",
      acompanhamento: "Deseja que eu verifique se a sua escala de hoje já está liberada na central?"
    },
    timestamp: new Date("2026-08-20T10:02:14.000Z"),
    metadata: {
      trace_id: "uuid-da-execucao-002",
      tokens_used: 165,
      latency_ms: 410
    }
  },

  // --- Sessão 002: Consulta com acionamento de Tool Call (Telemetria/Refrigeração) ---
  {
    thread_id: "eficientia_sessao_002",
    role: "user",
    content: "Qual a temperatura atual da carreta frigorífica no compartimento de suínos?",
    timestamp: new Date("2026-08-20T14:01:00.000Z"),
    metadata: {
      trace_id: "uuid-da-execucao-003"
    }
  },
  {
    thread_id: "eficientia_sessao_002",
    role: "assistant",
    agente_origem: "orquestrador",
    content: "A temperatura atual registrada pelos sensores é de 18.5°C, perfeitamente em conformidade com as diretrizes de bem-estar animal para transporte de carga viva.",
    tool_calls: [
      {
        tool: "obter_telemetria_tempo_real",
        parametros: { placa: "XYZ-9876", tipo_sensor: "temperatura_baia" }
      }
    ],
    tool_outputs: [
      {
        status: "sucesso",
        leitura_celsius: 18.5,
        faixa_segura: true
      }
    ],
    json_orquestrador: {
      dominio: "telemetria",
      intencao: "consultar_temperatura",
      resposta: "A temperatura atual registrada pelos sensores é de 18.5°C, perfeitamente em conformidade com as normas.",
      acompanhamento: "Deseja ativar alertas em tempo real se a temperatura variar mais de 2°C?"
    },
    timestamp: new Date("2026-08-20T14:01:06.000Z"),
    metadata: {
      trace_id: "uuid-da-execucao-003",
      tokens_used: 210,
      latency_ms: 620
    }
  }
];

const messagesResult = currentDb.messages.insertMany(messagesData);
print(`[MongoDB] ${Object.keys(messagesResult.insertedIds).length} mensagens inseridas com sucesso.`);

print("\n[MongoDB] Carga de dados (Seed) finalizada com êxito.");
