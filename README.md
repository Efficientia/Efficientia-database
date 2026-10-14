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
│   └── (Estrutura da aplicação de filas de eventos e leaderboards em tempo real)
│
├── 03_mongodb/                 # Banco Conversacional e Não-Estruturado [MD-50]
│   └── (Futuro: Interações conversacionais e dados semiestruturados)
│
└── 04_neo4j/                   # Banco em Grafo [MD-52]
    └── (Futuro: Rastreabilidade de redes logísticas e traversals em grafos)
```

---

## 🚀 Tecnologias e Serviços

- **PostgreSQL / Supabase**: Fonte da verdade transacional, modelagem relacional normalizada (3FN), catálogo de governança e camada analítica via Star Schema.
- **Redis / Upstash**: Processamento assíncrono de eventos através de Redis Streams, cache e rankings em tempo real com Sorted Sets.
- **Python**: Serviços de integração, workers de filas e reconciliação de dados.
