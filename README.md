# Efficientia - Arquitetura de Dados Multimodelo

Repositório central de modelagem, migrações e rotinas de banco de dados do ecossistema **Efficientia**, focado na gestão logística e bem-estar animal no transporte pecuário (da fazenda ao frigorífico).

---

## 🏛️ Estrutura Arquitetural por Tecnologia

O projeto adota uma arquitetura multimodelo (*Polyglot Persistence*), separando cada motor de banco de dados de acordo com sua responsabilidade estratégica:

```text
Efficientia-database/
├── .gitignore                  # Ignora ambientes virtuais, caches e credenciais locais
├── README.md                   # Visão geral da arquitetura do repositório
│
├── 01_postgresql/              # Núcleo Transacional (ACID) & Camada Analítica (Supabase)
│   ├── .env.example            # Variáveis de ambiente de conexão do PostgreSQL
│   ├── README.md               # Documentação e ordem de compilação dos scripts
│   ├── 01_ddl/                 # Schemas, tipos enumerados e tabelas estruturais
│   ├── 02_constraints_and_indexes/ # Índices de performance e FKs
│   ├── 03_views/               # Camada Dimensional (Star Schema) e Materialized Views
│   ├── 04_functions/           # Funções e gatilhos de auditoria/regras
│   ├── 05_triggers/            # Gatilhos automáticos de validação e auditoria
│   ├── 06_procedures/          # Stored Procedures para transações críticas
│   └── 07_dataload/            # Cargas DML iniciais (Catálogo de Dados e Domínios)
│
├── 02_redis/                   # Sistema de Filas & Ranking em Tempo Real (Upstash) [MD-51]
│   ├── .env.example            # Variáveis de ambiente do Redis e Upstash
│   ├── README.md               # Documentação da fila, streams e comandos
│   ├── requirements.txt        # Dependências do driver Redis, psycopg e testes
│   ├── main.py                 # CLI de execução do Outbox Relay e Workers
│   ├── src/                    # Implementação de Outbox Relay, Consumer Groups e Jobs
│   └── tests/                  # Testes automatizados com fakeredis
│
├── 03_mongodb/                 # Banco Conversacional e Não-Estruturado (IA) [MD-50]
│   ├── README.md               # Modelagem documental, padrão de referência e guia mongosh
│   ├── 01_schema_validation.js # Validação estrita de schema ($jsonSchema)
│   ├── 02_indexes.js           # Índices de performance e ordenação do chat
│   ├── 03_seed_conversations.js # Carga de dados (threads e mensagens do orquestrador)
│   └── 04_conversational_queries.js # Contexto LLM, FinOps/tokens e dores da frota
│
└── 04_neo4j/                   # Banco em Grafo [MD-52]
    ├── README.md               # Modelagem do Grafo de Propriedades e análise de Traversal
    ├── 01_schema_constraints.cypher # Constraints de unicidade e índices de nós
    ├── 02_seed_data.cypher     # Carga de malha pecuária e vetores de contaminação cruzada
    └── 03_traversal_queries.cypher  # Consultas de Traversal para rastreabilidade epidemiológica
```

---

## 🚀 Tecnologias e Serviços

- **PostgreSQL / Supabase**: Fonte da verdade transacional, modelagem relacional normalizada (3FN), catálogo de governança e camada analítica via Star Schema.
- **Redis / Upstash**: Processamento assíncrono de eventos através de Redis Streams, cache e rankings em tempo real com Sorted Sets.
- **MongoDB**: Repositório de documentos flexíveis para interações conversacionais da IA, histórico de chat, telemetria de tokens e observabilidade.
- **Neo4j**: Banco em grafo para análise de rede pecuária, rastreabilidade epidemiológica e consultas com *graph traversal*.
- **Python**: Serviços de integração, workers de filas e reconciliação de dados.
