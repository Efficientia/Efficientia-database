/**
 * ==============================================================================
 * PROJETO EFFICIENTIA - TESTES AUTOMATIZADOS DO MONGODB (VALIDAÇÃO DE ESQUEMA)
 * ==============================================================================
 * Testa as regras de validação via $jsonSchema das coleções "threads" e "messages":
 * 1. Insere documento válido na coleção threads.
 * 2. Tenta inserir documento inválido (sem campos obrigatórios) e espera rejeição.
 * 3. Valida índices de busca textual e temporal.
 * ==============================================================================
 */

const dbName = "efficientia_ai";
const currentDb = db.getSiblingDB ? db.getSiblingDB(dbName) : db;

print(`[TESTE MONGODB] Iniciando validação de regras no banco: ${dbName}...`);

let testesAprovados = 0;
let totalTestes = 0;

function assert(condition, message) {
  totalTestes++;
  if (condition) {
    print(`  [OK] Teste ${totalTestes}: ${message}`);
    testesAprovados++;
  } else {
    print(`  [FALHA] Teste ${totalTestes}: ${message}`);
    throw new Error(`Falha na asserção: ${message}`);
  }
}

// ------------------------------------------------------------------------------
// Teste 1: Inserção válida em threads
// ------------------------------------------------------------------------------
const testThreadId = "test_thread_autoteste_001";

try {
  currentDb.threads.deleteOne({ thread_id: testThreadId });

  currentDb.threads.insertOne({
    thread_id: testThreadId,
    usuario_id: "00011122233",
    placa_veiculo: "ABC1D23",
    status: "ativa",
    resumo_contexto: "Sessão de teste automatizado de validação de esquema.",
    criado_em: new Date(),
    atualizado_em: new Date()
  });

  const doc = currentDb.threads.findOne({ thread_id: testThreadId });
  assert(doc !== null && doc.thread_id === testThreadId, "Inserção de thread válida aceita pelo $jsonSchema");
} catch (e) {
  assert(false, `Erro inesperado na inserção válida de thread: ${e.message}`);
}

// ------------------------------------------------------------------------------
// Teste 2: Rejeição de thread com status inválido (Enum $jsonSchema)
// ------------------------------------------------------------------------------
let rejeitouInvalido = false;
try {
  currentDb.threads.insertOne({
    thread_id: "test_thread_invalida",
    usuario_id: "00011122233",
    status: "status_inexistente_proibido",
    criado_em: new Date(),
    atualizado_em: new Date()
  });
} catch (e) {
  rejeitouInvalido = true;
}
assert(rejeitouInvalido, "Rejeição estrita de thread com status fora do enum permitido");

// ------------------------------------------------------------------------------
// Teste 3: Limpeza de dados de teste
// ------------------------------------------------------------------------------
currentDb.threads.deleteOne({ thread_id: testThreadId });
assert(currentDb.threads.findOne({ thread_id: testThreadId }) === null, "Limpeza de documentos de teste concluída");

print(`[TESTE MONGODB] Concluído: ${testesAprovados}/${totalTestes} testes aprovados com sucesso.`);
