# Efficientia - Camada Conversacional e Orquestração de IA (MongoDB)

Módulo responsável pela persistência documental semiestruturada, gestão de sessões de atendimento, memória contextual de curto e longo prazo de Modelos de Linguagem de Grande Escala (LLM), rastreamento de chamadas de ferramentas (*Tool Calling*) e observabilidade financeira e operacional (*FinOps* e *APM*) do Agente Orquestrador de Inteligência Artificial da plataforma **Efficientia**, implementado em **MongoDB** sobre o banco de dados `efficientia_ai`.

---

## 1. Visão Geral e Escopo Estratégico

Durante a operação logística de transporte de animais vivos, motoristas e equipes de campo interagem em linguagem natural com o assistente inteligente da plataforma para esclarecer procedimentos operacionais do aplicativo (como preenchimento de horários e odômetro) e consultar leituras em tempo real de sensores embarcados (como temperatura das baias de carga viva).

Diferentemente dos registros contábeis e fiscais do transporte, diálogos assistidos por Inteligência Artificial apresentam estruturas polimórficas: mensagens enviadas por humanos possuem apenas texto e identificador de rastreio, ao passo que respostas geradas pelo agente orquestrador podem conter listas variáveis de ferramentas acionadas (`tool_calls`), retornos dinâmicos de sensores (`tool_outputs`), objetos semânticos de classificação de intenção (`json_orquestrador`) e métricas de telemetria computacional (`metadata`).

O escopo construído neste diretório abrange quatro frentes completas em JavaScript nativo para `mongosh`:

1. **Governança Estrutural com Validação Estrita (`01_schema_validation.js`)**: Criação das coleções `threads` e `messages` equipadas com validadores nativos `$jsonSchema` configurados em nível `strict` e ação `error`, assegurando contratos rigorosos de tipos BSON, campos obrigatórios e domínios enumerados sem sacrificar a extensibilidade dos arrays de ferramentas.
2. **Indexação Especializada de Baixa Latência (`02_indexes.js`)**: Definição de 7 índices estratégicos (único, simples e compostos seguindo a regra *Equality, Sort, Range*) que eliminam ordenações em memória (*in-memory sort*) na montagem da janela de contexto do LLM e aceleram auditorias de rastreamento distribuído.
3. **Carga Idempotente de Diálogos Realistas (`03_seed_conversations.js`)**: Povoamento reproduzível de sessões ativas e encerradas, cobrindo diálogos multi-turno de suporte ao condutor e fluxos completos de invocação de ferramentas de telemetria veicular.
4. **Consultas Operacionais e *Aggregation Pipelines* (`04_conversational_queries.js`)**: Implementação de 4 consultas analíticas e transacionais para reconstrução cronológica de prompt, recuperação de sessão ativa com junção `$lookup` da última mensagem, cálculo de custo de tokens e latência (*FinOps*/SLO) e mapeamento das principais dúvidas operacionais da frota.

---

## 2. Estrutura Arquitetural de Diretórios

Os scripts seguem numeração sequencial correspondente à ordem exata de configuração estrutural, indexação, carga inicial e extração analítica:

```text
03_mongodb/
├── README.md                                     # Documentação técnica completa e modelo conceitual documental
├── 01_schema_validation.js                       # Criação das coleções threads e messages com regras $jsonSchema
├── 02_indexes.js                                 # Criação dos 7 índices operacionais, temporais, únicos e analíticos
├── 03_seed_conversations.js                      # Carga idempotente de sessões e turnos conversacionais com tool calls
├── 04_conversational_queries.js                  # Consultas de contexto LLM e pipelines de agregação (FinOps e intenções)
├── 05_rollback.js                                # Script de desfazimento seguro de coleções e índices
└── tests/                                        # Baterias de testes automatizados
    └── check_mongodb.js                          # Teste automatizado de validação de esquema ($jsonSchema)
```

---

## 3. Modelo Conceitual

No paradigma orientado a documentos, o modelo conceitual distingue explicitamente **coleções independentes conectadas por chaves de referência documental** (*Document Referencing*) de **subdocumentos e vetores aninhados por composição física** (*Embedding*) no interior de um único documento BSON, além das **chaves lógicas externas** que conectam a conversa às entidades mestras do ecossistema.

### 3.1 Diagrama Conceitual de Coleções, Documentos, Subdocumentos, Chaves e Relações

```mermaid
erDiagram
    ENTIDADE_EXTERNA_USUARIO ||--o{ COLECAO_THREADS : "identifica condutor (usuario_id = cpf)"
    ENTIDADE_EXTERNA_VEICULO ||--o{ COLECAO_THREADS : "vincula implemento (placa_veiculo = placa)"

    COLECAO_THREADS ||--o{ COLECAO_MESSAGES : "referência documental 1:N (thread_id)"

    COLECAO_MESSAGES ||--o| SUBDOC_JSON_ORQUESTRADOR : "embute 1:1 (composição BSON)"
    COLECAO_MESSAGES ||--o| SUBDOC_METADATA : "embute 1:1 (composição BSON)"
    COLECAO_MESSAGES ||--o{ ARRAY_TOOL_CALLS : "embute 1:N (array de objetos)"
    COLECAO_MESSAGES ||--o{ ARRAY_TOOL_OUTPUTS : "embute 1:N (array de objetos)"

    ENTIDADE_EXTERNA_USUARIO {
        string cpf PK "Chave lógica oriunda do domínio corporativo"
    }

    ENTIDADE_EXTERNA_VEICULO {
        string placa PK "Chave lógica oriunda do domínio de frota"
    }

    COLECAO_THREADS {
        objectId _id PK "Identificador físico nativo BSON"
        string thread_id UK "Chave única de sessão (obrigatório)"
        string usuario_id FK "CPF ou identificador do motorista (obrigatório)"
        string placa_veiculo FK "Placa do veículo em operação (opcional)"
        string status "ENUM: ativa | encerrada | arquivada (obrigatório)"
        date criado_em "Data/hora de abertura da sessão (obrigatório)"
        date atualizado_em "Data/hora da última interação (obrigatório)"
    }

    COLECAO_MESSAGES {
        objectId _id PK "Identificador físico nativo BSON"
        string thread_id FK "Referência para threads.thread_id (obrigatório)"
        string role "ENUM: user | assistant | system | tool (obrigatório)"
        string agente_origem "Identificador do agente IA (ex: orquestrador)"
        string content "Conteúdo textual da mensagem (obrigatório)"
        date timestamp "Instante exato do turno conversacional (obrigatório)"
    }

    SUBDOC_JSON_ORQUESTRADOR {
        string dominio "Categoria operacional (ex: motorista, telemetria)"
        string intencao "Intenção classificada (ex: consultar_temperatura)"
        string resposta "Síntese objetiva elaborada pelo agente"
        string acompanhamento "Pergunta proativa de continuidade"
    }

    SUBDOC_METADATA {
        string trace_id "Identificador de rastreamento distribuído APM"
        number tokens_used "Total de tokens consumidos (int, long ou double)"
        number latency_ms "Tempo de inferência em milissegundos"
    }

    ARRAY_TOOL_CALLS {
        string tool "Nome da função externa invocada pelo LLM"
        object parametros "Argumentos dinâmicos enviados à ferramenta"
    }

    ARRAY_TOOL_OUTPUTS {
        string status "Resultado da chamada da ferramenta"
        double leitura_celsius "Exemplo de propriedade dinâmica retornada"
        boolean faixa_segura "Indicador de conformidade sanitária"
    }
```

### 3.2 Diagrama Conceitual da Estrutura Hierárquica BSON (Referência vs. Embutimento)

```mermaid
flowchart LR
    subgraph Col_Threads ["Coleção: threads (Cabeçalho Leve)"]
        DOC_T["Documento Thread (PK: _id | UK: thread_id)"]
        PROP_T["Propriedades Raiz: usuario_id, placa_veiculo, status, criado_em, atualizado_em"]
        DOC_T --- PROP_T
    end

    subgraph Col_Messages ["Coleção: messages (Turnos Imutáveis Append-Only)"]
        DOC_M["Documento Message (PK: _id | FK: thread_id)"]
        PROP_M["Propriedades Escalares: role, agente_origem, content, timestamp"]
        EMB_ORQ["Subdocumento Embutido: json_orquestrador (dominio, intencao, resposta, acompanhamento)"]
        EMB_MET["Subdocumento Embutido: metadata (trace_id, tokens_used, latency_ms)"]
        EMB_TC["Array Embutido: tool_calls[] (chamadas de funções externas)"]
        EMB_TO["Array Embutido: tool_outputs[] (respostas brutas de sensores/APIs)"]

        DOC_M --- PROP_M
        DOC_M --> EMB_ORQ
        DOC_M --> EMB_MET
        DOC_M --> EMB_TC
        DOC_M --> EMB_TO
    end

    DOC_T ==>|"Relação 1:N por Referência (thread_id)"| DOC_M
```

---

## 4. Arquitetura Técnica e Fluxo de Funcionamento

### 4.1 Justificativa do Padrão Híbrido (Referência `1:N` + Subdocumentos Embutidos)

Em aplicações conversacionais, embutir todo o vetor de mensagens dentro do documento `threads` constitui um antipadrão (*Unbounded Array Growth*): o documento cresce continuamente a cada turno, sofre realocações custosas em disco e corre risco de atingir o teto físico de **16 MB por documento BSON**.

A arquitetura implementada resolve esse problema combinando dois padrões complementares:

1. **Particionamento por Referência (`threads` $\leftarrow$ `messages`)**:
   * A coleção `threads` permanece enxuta e de tamanho fixo, permitindo atualizações rápidas de `status` e `atualizado_em` quando o motorista abre ou encerra o atendimento no aplicativo móvel.
   * A coleção `messages` opera sob padrão *Append-Only* (apenas inserções sequenciais imutáveis), escalando horizontalmente para milhões de mensagens sem degradação de escrita.
2. **Composição Embutida por Turno (`json_orquestrador`, `metadata`, `tool_calls`, `tool_outputs`)**:
   * Como as chamadas de ferramentas, os metadados de consumo de tokens e a interpretação semântica pertencem intrinsecamente a uma única resposta do modelo e são sempre lidos em conjunto com ela, mantê-los aninhados dentro do próprio documento `messages` garante atomicidade de gravação em uma única operação `insertOne` / `insertMany`, dispensando junções para auditoria de turnos individuais.

### 4.2 Fluxo Operacional de Atendimento e Telemetria

```mermaid
sequenceDiagram
    autonumber
    participant App as Aplicativo do Motorista
    participant Orq as Agente Orquestrador (LLM)
    participant Tool as Serviço de Telemetria / Frota
    participant Mongo as MongoDB (efficientia_ai)

    App->>Mongo: Consulta 2 ($lookup): Busca thread 'ativa' por usuario_id + última mensagem
    Mongo-->>App: Retorna cabeçalho da sessão e contexto imediato
    App->>Mongo: Insere documento em 'messages' (role: 'user', trace_id)
    Orq->>Mongo: Consulta 1 (find + sort): Carrega histórico cronológico via idx_messages_thread_timestamp_asc
    Mongo-->>Orq: Lista ordenada de mensagens sem sort em memória
    opt Pergunta exige leitura de sensor embarcado
        Orq->>Tool: Executa obter_telemetria_tempo_real(placa, temperatura_baia)
        Tool-->>Orq: Retorna {leitura_celsius: 18.5, faixa_segura: true}
    end
    Orq->>Mongo: Insere documento em 'messages' (role: 'assistant', tool_calls, tool_outputs, json_orquestrador, metadata)
    Note over Mongo: Validador $jsonSchema (strict / error) inspeciona tipos BSON e enums antes do commit
    Orq->>Mongo: Atualiza 'threads.atualizado_em'
```

---

## 5. Especificação Técnica e Catálogo de Componentes

### 5.1 Contratos de Validação `$jsonSchema` (`01_schema_validation.js`)

Ambas as coleções utilizam `validationLevel: "strict"` (aplica regras tanto em inserções quanto em atualizações) e `validationAction: "error"` (rejeita imediatamente qualquer documento fora de conformidade).

#### Coleção `threads`

| Campo | Tipo BSON | Obrigatório | Restrições / Domínio | Finalidade no Modelo |
| :--- | :--- | :---: | :--- | :--- |
| `_id` | `objectId` | Automático | Chave primária física gerada pelo motor | Identificador único interno do documento |
| `thread_id` | `string` | Sim | Índice único (`idx_threads_thread_id_unique`) | Chave de negócio da sessão conversacional |
| `usuario_id` | `string` | Sim | Chave lógica externa (`tb_usuario.cpf`) | Identificação do motorista ou operador autenticado |
| `placa_veiculo` | `string` | Não | Chave lógica externa (`tb_veiculo_base.placa`) | Placa do caminhão ou carreta vinculada ao atendimento |
| `status` | `string` | Sim | `enum: ["ativa", "encerrada", "arquivada"]` | Controle do ciclo de vida da conversa |
| `criado_em` | `date` | Sim | Instante UTC de abertura | Auditoria temporal de início do chamado |
| `atualizado_em` | `date` | Sim | Instante UTC do último evento | Ordenação de conversas recentes no painel operacional |

#### Coleção `messages`

| Campo / Caminho | Tipo BSON | Obrigatório | Restrições / Domínio | Finalidade no Modelo |
| :--- | :--- | :---: | :--- | :--- |
| `_id` | `objectId` | Automático | Chave primária física gerada pelo motor | Identificador único do turno de mensagem |
| `thread_id` | `string` | Sim | Referência para `threads.thread_id` | Agrupador lógico das mensagens da mesma sessão |
| `role` | `string` | Sim | `enum: ["user", "assistant", "system", "tool"]` | Papel do emissor conforme padrão de APIs de LLM |
| `agente_origem` | `string` | Não | Ex.: `"orquestrador"` | Identificação do agente especialista responsável pela resposta |
| `content` | `string` | Sim | Texto livre não vazio | Mensagem renderizada ao motorista ou enviada por ele |
| `tool_calls` | `array<object>` | Não | Itens validados como `bsonType: "object"` | Registro auditável das funções externas invocadas pelo modelo |
| `tool_outputs` | `array<object>` | Não | Itens validados como `bsonType: "object"` | Respostas brutas devolvidas pelas integrações acionadas |
| `json_orquestrador` | `object` | Não | Propriedades `string`: `dominio`, `intencao`, `resposta`, `acompanhamento` | Saída estruturada para roteamento semântico e sugestão proativa |
| `timestamp` | `date` | Sim | Instante UTC exato da mensagem | Ordenação cronológica estrita do diálogo |
| `metadata` | `object` | Não | `trace_id` (`string`), `tokens_used` e `latency_ms` (`int \| long \| double`) | Telemetria de observabilidade distribuída e controle de custos |

### 5.2 Catálogo dos 7 Índices Estratégicos (`02_indexes.js`)

| Coleção | Nome do Índice | Definição de Chaves | Tipo | Propósito de Otimização |
| :--- | :--- | :--- | :--- | :--- |
| `threads` | `idx_threads_thread_id_unique` | `{ thread_id: 1 }` | Simples + Único | Garante integridade de chave candidata e acelera o `$lookup` |
| `threads` | `idx_threads_usuario_status` | `{ usuario_id: 1, status: 1 }` | Composto (ESR) | Localiza instantaneamente a sessão `"ativa"` do motorista ao abrir o app |
| `threads` | `idx_threads_placa_veiculo` | `{ placa_veiculo: 1 }` | Simples | Recupera histórico de ocorrências conversacionais associadas a um veículo |
| `threads` | `idx_threads_atualizado_em_desc` | `{ atualizado_em: -1 }` | Simples Decrescente | Alimenta listagens de monitoramento em tempo real das conversas mais recentes |
| `messages` | `idx_messages_thread_timestamp_asc` | `{ thread_id: 1, timestamp: 1 }` | Composto (ESR) | Índice crítico: entrega o histórico do chat já ordenado em disco sem *Sort* em memória |
| `messages` | `idx_messages_metadata_trace_id` | `{ "metadata.trace_id": 1 }` | *Dot Notation* | Correlaciona logs de infraestrutura e rastreamento distribuído (OpenTelemetry) |
| `messages` | `idx_messages_orquestrador_dominio_intencao` | `{ "json_orquestrador.dominio": 1, "json_orquestrador.intencao": 1 }` | Composto em Subdocumento | Acelera agregações analíticas de dúvidas frequentes por área operacional |

### 5.3 Cenários de Carga Inicial (`03_seed_conversations.js`)

| Sessão (`thread_id`) | Motorista (`usuario_id`) | Veículo | Status | Turnos Carregados e Recursos Demonstrados |
| :--- | :--- | :--- | :--- | :--- |
| `eficientia_sessao_001` | `123.456.789-00` | `ABC-1234` | `ativa` | 4 mensagens (2 turnos completos) no domínio `"motorista"` / intenção `"esclarecer_preenchimento"`, orientando sobre preenchimento automático de embarque e lançamento do odômetro inicial |
| `eficientia_sessao_002` | `987.654.321-11` | `XYZ-9876` | `encerrada` | 2 mensagens (1 turno completo) no domínio `"telemetria"` / intenção `"consultar_temperatura"`, demonstrando invocação de `obter_telemetria_tempo_real` e validação de conformidade térmica (`18.5°C`) |

### 5.4 Consultas e *Aggregation Pipelines* (`04_conversational_queries.js`)

| Identificação | Operadores Utilizados | Pergunta Operacional ou Gerencial Respondida |
| :--- | :--- | :--- |
| **Consulta 1: Contexto para LLM** | `find()`, projeção `{ _id: 0, ... }`, `sort({ timestamp: 1 })` | Quais mensagens compõem, na ordem exata, a memória da sessão `eficientia_sessao_001` para envio ao modelo? |
| **Consulta 2: Sessão Ativa do Condutor** | `$match`, `$lookup` com sub-pipeline (`let`, `$expr`, `$eq`, `$sort`, `$limit: 1`), `$unwind` | Qual é a conversa ativa do motorista `123.456.789-00` e qual foi a última mensagem trocada nela? |
| **Consulta 3: Observabilidade e FinOps** | `$match` (`$exists`), `$group` (`$sum`, `$avg`, `$max`), `$project` (`$round`) | Qual é o volume total de respostas, consumo acumulado/médio de tokens e latência média/máxima por agente de IA? |
| **Consulta 4: Ranking de Intenções** | `$match`, `$group` composto (`dominio`, `intencao`, `$first`), `$sort`, `$project` | Quais domínios operacionais e dúvidas geram maior volume de acionamentos na frota? |

---

## 6. Requisitos e Configuração de Ambiente

### 6.1 Pré-Requisitos

* **Servidor MongoDB 6.0 ou superior** em execução local ou remota.
* **MongoDB Shell (`mongosh`)** instalado no terminal para execução dos scripts `.js`.
* Opcionalmente, cliente visual compatível (como MongoDB Compass) para inspeção gráfica dos documentos BSON, validadores e planos de execução (`explain("executionStats")`).

### 6.2 Parâmetros de Conexão

Os quatro scripts selecionam automaticamente o banco de dados `efficientia_ai` por meio da instrução `db.getSiblingDB("efficientia_ai")`, podendo receber qualquer URI padrão do protocolo MongoDB na linha de comando:

```ini
# Conexão local padrão sem autenticação
MONGODB_URI=mongodb://localhost:27017/efficientia_ai

# Conexão autenticada em servidor dedicado
MONGODB_URI=mongodb://usuario:senha_segura@servidor-mongodb:27017/efficientia_ai?authSource=admin
```

---

## 7. Roteiro de Implantação e Execução

### 7.1 Execução Sequencial via Linha de Comando (`mongosh`)

A partir da raiz do repositório, execute os quatro arquivos na ordem abaixo:

```bash
# 1. Criar as coleções 'threads' e 'messages' com validação $jsonSchema estrita
mongosh "$MONGODB_URI" 03_mongodb/01_schema_validation.js

# 2. Criar os 7 índices operacionais, únicos e compostos
mongosh "$MONGODB_URI" 03_mongodb/02_indexes.js

# 3. Popular as conversas iniciais e interações com tool calls (execução idempotente)
mongosh "$MONGODB_URI" 03_mongodb/03_seed_conversations.js

# 4. Executar as 4 consultas demonstrativas e pipelines analíticos
mongosh "$MONGODB_URI" 03_mongodb/04_conversational_queries.js
```

### 7.2 Execução Interativa Dentro do Shell

Caso já esteja conectado a uma sessão interativa do `mongosh`, carregue os artefatos diretamente com a função `load()`:

```javascript
use("efficientia_ai");
load("03_mongodb/01_schema_validation.js");
load("03_mongodb/02_indexes.js");
load("03_mongodb/03_seed_conversations.js");
load("03_mongodb/04_conversational_queries.js");
```

### 7.3 Verificação do Uso de Índice sem Ordenação em Memória

```javascript
use("efficientia_ai");
db.messages
  .find({ thread_id: "eficientia_sessao_001" })
  .sort({ timestamp: 1 })
  .explain("executionStats");
// Confirma o estágio IXSCAN sobre 'idx_messages_thread_timestamp_asc' sem estágio SORT em RAM.
```

---

## 8. Governança, Concorrência, Segurança e Qualidade

* **Contrato de Dados Defensivo (*Schema-on-Write*)**: Embora o MongoDB seja um banco orientado a documentos, o uso de `$jsonSchema` com `validationLevel: "strict"` e `validationAction: "error"` impede que falhas de serialização na aplicação gravem mensagens sem `thread_id`, `role` inválido ou datas em formato textual incorreto.
* **Flexibilidade Numérica Interoperável**: Os atributos `metadata.tokens_used` e `metadata.latency_ms` aceitam explicitamente `["int", "long", "double"]`, prevenindo rejeições espúrias causadas pelas diferenças de representação numérica entre drivers Python, Node.js, Java e `mongosh`.
* **Idempotência de Testes e Carga**: Tanto `01_schema_validation.js` (recriação limpa de coleções) quanto `03_seed_conversations.js` (limpeza prévia via `deleteMany({})`) e `02_indexes.js` (`createIndex` nativamente idempotente) podem ser reexecutados repetidamente sem gerar duplicidade de dados ou conflitos de chave única.
* **Auditabilidade Completa de Agentes Autônomos**: O armazenamento conjunto de `tool_calls`, `tool_outputs` e `metadata.trace_id` permite reconstituir com exatidão quais leituras de sensores fundamentaram cada orientação dada ao motorista em trânsito.
