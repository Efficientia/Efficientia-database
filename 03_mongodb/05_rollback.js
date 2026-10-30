/**
 * ==============================================================================
 * PROJETO EFFICIENTIA - SCRIPT DE ROLLBACK DO MONGODB
 * ==============================================================================
 * Executa o desfazimento seguro das coleções e índices da base conversacional
 * da Inteligência Artificial (banco: efficientia_ai).
 * ==============================================================================
 */

const dbName = "efficientia_ai";
const currentDb = db.getSiblingDB ? db.getSiblingDB(dbName) : db;

print(`[MongoDB Rollback] Iniciando processo de desfazimento no banco: ${dbName}...`);

try {
  const collections = currentDb.getCollectionNames();
  
  if (collections.includes("messages")) {
    print("[MongoDB Rollback] Removendo coleção 'messages' e seus respectivos índices...");
    currentDb.messages.drop();
    print("[MongoDB Rollback] Coleção 'messages' removida com sucesso.");
  } else {
    print("[MongoDB Rollback] Coleção 'messages' não existe. Ignorando.");
  }

  if (collections.includes("threads")) {
    print("[MongoDB Rollback] Removendo coleção 'threads' e seus respectivos índices...");
    currentDb.threads.drop();
    print("[MongoDB Rollback] Coleção 'threads' removida com sucesso.");
  } else {
    print("[MongoDB Rollback] Coleção 'threads' não existe. Ignorando.");
  }

  print("[MongoDB Rollback] Desfazimento concluído com êxito.");
} catch (error) {
  print(`[MongoDB Rollback ERRO] Falha durante a execução: ${error.message}`);
  throw error;
}
