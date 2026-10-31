# Efficientia - Arquitetura e Engenharia de Dados

Repositório central de modelagem conceitual, lógica e física, mensageria assíncrona, processamento em memória, persistência documental e análise em grafos do ecossistema **Efficientia**, plataforma dedicada à gestão logística de precisão, rastreabilidade sanitária e bem-estar animal no transporte pecuário entre propriedades rurais e unidades frigoríficas.

---

## 1. Visão Geral e Escopo Estratégico

A plataforma **Efficientia** governa todo o ciclo operacional e sanitário do transporte de carga viva, compreendendo o cadastro corporativo e de frota, o embarque na fazenda fornecedora, o registro de paradas imprevistas em rodovia, o desembarque na unidade frigorífica, a inspeção veterinária com parecer técnico, o suporte conversacional aos motoristas assistido por Inteligência Artificial e o rastreamento epidemiológico da malha logística.

Para atender simultaneamente aos requisitos de integridade transacional estrita, mensageria orientada a eventos em tempo real, flexibilidade para estruturas conversacionais semiestruturadas e travessia eficiente de redes complexas, o projeto implementa uma **arquitetura multimodelo** composta por quatro motores de banco de dados especializados e complementares:

* **PostgreSQL (`01_postgresql/`)**: Núcleo transacional relacional (ACID) responsável pelos domínios corporativo, herança de frota, relatórios de viagem, paradas, anomalias sanitárias, catálogo de metadados ativos, auditoria imutável em JSONB, publicação transacional de eventos (*Transactional Outbox*) e camada analítica dimensional (*Star Schema* e *Materialized View* mensal).
* **Redis (`02_redis/`)**: Camada de estruturas de dados em memória e mensageria assíncrona responsável pela fila de eventos operacionais (*Streams* e *Consumer Groups*), fila de mensagens mortas (*Dead Letter Queue*), placares competitivos e operacionais em tempo real (*Sorted Sets* e *Hashes*), cache de configurações de nível de serviço (*Cache-Aside*) e controle de taxa de requisições (*Fixed Window Rate Limiting*).
* **MongoDB (`03_mongodb/`)**: Banco de dados orientado a documentos BSON dedicado à camada conversacional do Agente Orquestrador de Inteligência Artificial (`efficientia_ai`), armazenando sessões de atendimento (`threads`), turnos de diálogo (`messages`), chamadas e retornos de ferramentas (*tool calls* e *tool outputs*), classificação semântica de intenções e telemetria de consumo de tokens e latência.
* **Neo4j (`04_neo4j/`)**: Banco de dados orientado a grafos de propriedades (*Property Graph Model*) voltado à inteligência sanitária, rastreabilidade epidemiológica (*Contact Tracing*), identificação de caminhos mínimos de contaminação cruzada pelo compartilhamento de cavalos mecânicos e carretas boiadeiras e cálculo de centralidade de risco na malha pecuária.

---

## 2. Estrutura Arquitetural de Diretórios

O repositório organiza cada paradigma de persistência em um diretório independente, numerado conforme a ordem lógica de implantação da infraestrutura de dados:

```text
Efficientia-database/
├── .github/                                      # Automações de Integração Contínua (CI/CD)
│   └── workflows/                                # Pipelines GitHub Actions para os 4 bancos de dados
│       ├── ci_postgresql.yml                     # Validação DDL, índices, carga e testes automatizados
│       ├── ci_redis.yml                          # Validação de configuração, scripts Lua e testes com pytest
│       ├── ci_mongodb.yml                        # Validação de regras $jsonSchema, índices e consultas
│       └── ci_neo4j.yml                          # Validação de constraints, projeções e travessias Cypher
├── .gitignore                                    # Regras de exclusão de ambientes virtuais, caches e credenciais
├── LICENSE                                       # Licença de uso do repositório
├── README.md                                     # Documentação arquitetural integrada e modelo conceitual global
│
├── 01_postgresql/                                # Núcleo Relacional Transacional (ACID) e Camada Dimensional (BI)
│   ├── .env.example                              # Modelo de variáveis de ambiente para conexão PostgreSQL
│   ├── README.md                                 # Documentação completa do banco relacional e modelo conceitual ER
│   ├── modelo_logico.pdf                         # Diagrama visual exportado do modelo lógico relacional
│   ├── modelo_logico_dbdiagram.dbml              # Código-fonte DBML da modelagem lógica relacional
│   ├── 01_ddl/                                   # Criação de schemas, tipos ENUM e tabelas com herança OO-SQL
│   │   ├── 01_schemas_e_tipos.sql                # Extensão pgcrypto, 4 schemas e 4 tipos enumerados
│   │   ├── 02_catalogo_e_auditoria.sql           # Catálogo ativo de metadados, log JSONB e monitoramento DAU
│   │   ├── 03_corporativo_e_frota.sql            # Endereços, empresas, SLA, usuários, fazendas, frigoríficos e frota
│   │   ├── 04_tabelas_transacionais.sql          # Domínios, relatórios de viagem, paradas, anomalias, análise e outbox
│   │   └── 05_governanca_backup_e_hierarquia.sql # Atributo LGPD, histórico de backup e hierarquia de anomalias
│   ├── 02_constraints_and_indexes/               # Otimização física de consultas e varreduras seletivas
│   │   └── 01_keys_e_indexes.sql                 # Índices B-Tree multi-tenant, chaves estrangeiras e índices parciais
│   ├── 03_views/                                 # Engenharia analítica, governança e Business Intelligence
│   │   ├── 01_datamart_bi.sql                    # 4 Views de Dimensão, 1 View de Fato e 1 Materialized View mensal
│   │   └── 02_views_governanca_dau_e_hierarquia.sql # Árvore recursiva, rollup de ocorrências, catálogo e DAU/MAU
│   ├── 04_functions/                             # Regras de negócio encapsuladas em PL/pgSQL
│   │   ├── 01_fn_registrar_auditoria.sql         # Captura automática de estado anterior/novo com expurgo de senha_hash
│   │   ├── 02_fn_registrar_dau.sql               # Contabilização idempotente de usuários ativos diários (DAU)
│   │   ├── 03_fn_validar_alocacao_viagem.sql     # Bloqueio preventivo de CNH e inspeções veiculares vencidas
│   │   ├── 04_fn_gerar_outbox_relatorio.sql      # Geração transacional de eventos JSONB para integração assíncrona
│   │   └── 05_fn_hierarquia_e_recuperacao.sql    # Função anti-ciclo, extrator de subárvore e volumetria pós-restore
│   ├── 05_triggers/                              # Gatilhos automáticos de governança, validação e mensageria
│   │   ├── 01_tg_auditoria.sql                   # Associação da auditoria às tabelas críticas corporativas e operacionais
│   │   ├── 02_tg_validacoes_operacionais.sql     # Gatilhos de validação pré-alocação e captura pós-evento no Outbox
│   │   └── 03_tg_hierarquia_anomalia.sql         # Gatilho de prevenção de ciclos e etapas na árvore de anomalias
│   ├── 06_procedures/                            # Transações atômicas com controle explícito de concorrência
│   │   ├── 01_sp_aprovar_relatorio.sql           # Aprovação veterinária com bloqueio pessimista (FOR UPDATE)
│   │   ├── 02_sp_registrar_anomalia.sql          # Registro validado e roteamento dinâmico de anomalias por etapa
│   │   └── 03_sp_governanca_e_recuperacao.sql    # Sincronização de catálogo, registro de backup e restore cirúrgico
│   ├── 07_dataload/                              # Carga massiva modular (>8.400 registros de simulação realista)
│   │   ├── 01_carga_catalogo_dados.sql           # População completa do dicionário de dados e perfis RBAC
│   │   ├── 02_carga_corporativo.sql              # Endereços, empresas, parâmetros de SLA e quadro de colaboradores
│   │   ├── 03_carga_frota_e_dominios.sql         # Cavalos, carretas, fazendas, frigoríficos e tabelas de domínio
│   │   ├── 04_carga_relatorios_viagem.sql        # 1.500 viagens completas com métricas de embarque e desembarque
│   │   ├── 05_carga_paradas_e_anomalias.sql      # Ocorrências rodoviárias e avarias de embarque e desembarque
│   │   ├── 06_carga_auditoria_analise.sql        # Pareceres técnicos de auditoria veterinária
│   │   ├── 07_carga_outbox_eventos.sql           # Eventos transacionais prontos para retransmissão assíncrona
│   │   ├── 08_carga_monitoramento_dau.sql        # Série histórica de acessos diários de usuários
│   │   └── 09_carga_complementar_governanca.sql  # Marcação LGPD, árvore hierárquica e histórico de backup
│   ├── 08_backup/                                # Procedimentos de cópia de segurança e recuperação
│   │   ├── backup.sh                             # Script de dump customizado (-Fc) com cálculo de SHA-256
│   │   └── restore.sh                            # Script de restauração limpa com conferência de integridade
│   ├── 09_rollback/                              # Scripts para desfazimento controlado
│   │   ├── 01_drop_views_e_rotinas.sql           # Remoção de visões, procedimentos e triggers
│   │   └── 02_drop_tudo.sql                      # Teardown completo de tabelas, tipos e esquemas
│   ├── 10_tests/                                 # Baterias de testes automatizados
│   │   ├── 01_test_regras_negocio_e_validacoes.sql # Testes de bloqueio de CNH, categorias e aprovação
│   │   ├── 02_test_hierarquia_recursiva.sql      # Testes anti-ciclo, validação de etapas e subárvore
│   │   ├── 03_test_auditoria_dau_e_recuperacao.sql # Testes de auditoria, registro DAU e restore cirúrgico
│   │   └── check_postgresql.sh                   # Runner automatizado em bash para integração contínua
│   └── docs/                                     # Documentação analítica e formal
│       ├── NORMALIZACAO.md                       # Prova formal de 1FN a 5FN por tabela
│       ├── verificacao_normalizacao.sql          # Script SQL de checagem de integridade relacional
│       ├── OTIMIZACAO_EXPLAIN_ANALYZE.md         # Análise de planos de execução antes e depois de índices
│       ├── explain_analyze.sql                   # Consultas reprodutíveis de planos de execução
│       └── BACKUP_E_RECUPERACAO.md               # Política de RPO/RTO e runbook de recuperação
│
├── 02_redis/                                     # Mensageria em Memória, Filas Distribuídas, Cache e Rankings
│   ├── .env.example                              # Modelo de variáveis de ambiente para Redis e PostgreSQL
│   ├── README.md                                 # Documentação completa das estruturas em memória e modelo conceitual
│   ├── requirements.txt                          # Dependências Python (redis, psycopg, pydantic-settings, fakeredis, pytest)
│   ├── main.py                                   # Interface de linha de comando (CLI) operacional com 7 subcomandos
│   ├── config/                                   # Configuração de referência de servidor
│   │   └── redis.conf                            # Diretivas noeviction, persistência AOF e portas de rede
│   ├── scripts/                                  # Scripts atômicos em linguagem Lua
│   │   ├── registrar_viagem_ranking.lua          # Atualização atômica combinada de hash e sorted sets
│   │   └── verificar_rate_limit.lua              # Algoritmo atômico de controle de requisições por janela temporal
│   ├── src/                                      # Código-fonte modularizado da camada de integração e memória
│   │   ├── config.py                             # Carregamento e validação centralizada de parâmetros de ambiente
│   │   ├── connection.py                         # Pool de conexões Redis (TCP/TLS) e fábrica de sessões PostgreSQL
│   │   ├── keys.py                               # Governança centralizada dos 9 padrões de chaves multi-tenant
│   │   ├── cache/                                # Padrão Cache-Aside de configurações e Rate Limiting (Fixed Window)
│   │   ├── jobs/                                 # Processadores de alertas de mortalidade, emergência e placares
│   │   ├── queues/                               # Consumidor resiliente com Consumer Groups e Dead Letter Queue
│   │   ├── ranking/                              # Gestão atômica de Sorted Sets/Hashes e reconciliação analítica
│   │   └── relay/                                # Publicador Transactional Outbox com FOR UPDATE SKIP LOCKED
│   └── tests/                                    # Suíte de testes unitários e integrados em memória (fakeredis)
│
├── 03_mongodb/                                   # Persistência Documental para Orquestração de IA Conversacional
│   ├── README.md                                 # Documentação completa da modelagem documental e modelo conceitual
│   ├── 01_schema_validation.js                   # Criação de coleções threads e messages com $jsonSchema estrito
│   ├── 02_indexes.js                             # Índices simples, compostos e únicos para contexto LLM e APM
│   ├── 03_seed_conversations.js                  # Carga idempotente de sessões, diálogos multi-turno e tool calls
│   ├── 04_conversational_queries.js              # Consultas operacionais e pipelines de agregação (FinOps e intenções)
│   ├── 05_rollback.js                            # Script de desfazimento seguro de coleções e índices
│   └── tests/                                    # Testes automatizados de validação de esquema
│       └── check_mongodb.js                      # Validador de conformidade e rejeição com $jsonSchema
│
└── 04_neo4j/                                     # Grafo de Propriedades para Rastreabilidade Sanitária e Logística
    ├── README.md                                 # Documentação completa da modelagem em grafo e modelo conceitual
    ├── 01_schema_constraints.cypher              # 6 restrições de unicidade e 3 índices de busca para travessias
    ├── 02_seed_data.cypher                       # Carga da malha pecuária e simulação de contaminação cruzada
    ├── 03_traversal_queries.cypher               # Algoritmos de Contact Tracing, shortestPath e centralidade de risco
    ├── 04_projection/                            # Projeções incrementais do Transactional Outbox (PostgreSQL -> Neo4j)
    │   ├── upsert_propriedade_e_frigorifico.cypher # Projeção parametrizada de fazendas e unidades industriais
    │   ├── upsert_frota_e_motorista.cypher       # Projeção parametrizada de condutores e veículos
    │   ├── upsert_viagem_aprovada.cypher         # Materialização de viagem e topologia relacional de rota
    │   └── remover_viagem_cancelada.cypher       # Desmaterialização (DETACH DELETE) de viagens estornadas
    ├── 05_rollback/                              # Scripts para desfazimento total do grafo
    │   └── drop_everything.cypher                # Exclusão segura de nós, relacionamentos, constraints e índices
    └── tests/                                    # Baterias de validação automatizada
        └── check_neo4j.sh                        # Script bash de execução e validação contínua via cypher-shell
```

---

## 3. Modelo Conceitual

O modelo conceitual global do ecossistema **Efficientia** unifica o domínio logístico-sanitário e projeta cada entidade para a representação nativa mais adequada à sua natureza computacional: **entidades e relações normalizadas** no PostgreSQL, **chaves hierárquicas e estruturas de dados em memória** no Redis, **coleções e documentos aninhados** no MongoDB e **nós rotulados conectados por relacionamentos direcionados com propriedades** no Neo4j.

### 3.1 Diagrama Conceitual Integrado Multimodelo

```mermaid
flowchart TD
    subgraph Dominio_Relacional ["Modelo Relacional (PostgreSQL): Entidades, Chaves e Relações"]
        E_EMP["Entidade: Empresa (PK: id UUID | UK: cnpj)"]
        E_CFG["Entidade: ConfiguracaoOperacao (PK: id | UK/FK: empresa_id | Props: SLAs e metas)"]
        E_USU["Entidade: Usuario (PK: id | FK: empresa_id | UK: cpf, email, cnh)"]
        E_FRO["Herança: VeiculoBase -> Cavalo / Carreta (PK: id | FK: empresa_id | UK: placa)"]
        E_LOC["Entidades: Fazenda / UnidadeFrigorifica (PK: id | FKs: endereco_id, responsavel_id)"]
        E_VIA["Entidade Central: RelatorioViagem (PK: id | 7 FKs | Props: GTA, NF, KMs, cabeças, status)"]
        E_OCO["Entidades: ParadaImprevista / Anomalias / AuditoriaAnalise (PK: id | FK: relatorio_id)"]
        E_OUT["Entidade: OutboxEvento (PK: id | Props: tipo_evento, payload JSONB)"]

        E_EMP -->|"1:1 configura"| E_CFG
        E_EMP -->|"1:N emprega"| E_USU
        E_EMP -->|"1:N detém"| E_FRO
        E_USU -->|"1:N conduz e audita"| E_VIA
        E_FRO -->|"1:N traciona e transporta"| E_VIA
        E_LOC -->|"1:N origina"| E_VIA
        E_VIA -->|"1:N registra"| E_OCO
        E_VIA -->|"1:N dispara"| E_OUT
    end

    subgraph Dominio_Memoria ["Modelo Chave-Valor (Redis): Chaves, Estruturas e Propriedades"]
        K_STR["Stream: efficientia:{env}:{empresa_id}:stream:eventos (Props: evento_id, tipo_evento, payload)"]
        K_DLQ["Stream DLQ: efficientia:{env}:{empresa_id}:stream:dlq (Props: original_id, failed_at_group)"]
        K_HSH["Hash: ...:stats:motorista:{ano_mes}:{motorista_id} (Fields: embarcados, mortos, viagens | TTL 90d)"]
        K_ZST["Sorted Sets: ...:ranking:{volume|mortalidade|descarga} (Member: id | Score: float)"]
        K_CAC["Strings: ...:config (JSON, TTL 1h) e ...:ratelimit:report:{usuario_id} (Int, TTL 60s)"]

        K_STR -->|"Falha de processamento"| K_DLQ
        K_STR -->|"Consumo assíncrono"| K_HSH
        K_HSH -->|"Cálculo ponderado"| K_ZST
    end

    subgraph Dominio_Documental ["Modelo Documental (MongoDB): Coleções, Documentos e Subdocumentos"]
        C_THR["Coleção: threads (PK: _id | UK: thread_id | FKs Lógicas: usuario_id, placa_veiculo)"]
        C_MSG["Coleção: messages (PK: _id | FK: thread_id | Subdocs: json_orquestrador, metadata, tool_calls)"]

        C_THR -->|"1:N referencia (thread_id)"| C_MSG
    end

    subgraph Dominio_Grafo ["Modelo em Grafo (Neo4j): Nós, Relacionamentos e Propriedades"]
        N_PEC["Nó (:Pecuarista) [UK: cpf | Props: id, nome]"]
        N_FAZ["Nó (:Fazenda) [UK: id | Props: nome, municipio, uf, area_hectares]"]
        N_VIA["Nó (:Viagem) [UK: numero_gta | Props: data_embarque, qtd_morto, laudo_sanitario_suspeito]"]
        N_VEI["Nó (:Veiculo) [UK: placa | Props: modelo, tipo, capacidade_cabecas]"]
        N_MOT["Nó (:Motorista) [UK: cnh | Props: id, nome, categoria]"]
        N_UFR["Nó (:UnidadeFrigorifica) [UK: nome | Props: id, municipio, uf, capacidade_diaria]"]

        N_PEC -->|"[:PROPRIETARIO_DE]"| N_FAZ
        N_VIA -->|"[:PARTIU_DE]"| N_FAZ
        N_VIA -->|"[:DESTINADA_A]"| N_UFR
        N_VIA -->|"[:CONDUZIDA_POR]"| N_MOT
        N_VIA -->|"[:UTILIZOU_VEICULO {compartimento}]"| N_VEI
    end

    E_OUT ==>|"Chave de Integração: empresa_id + relatorio_id"| K_STR
    E_CFG -.->|"Cache-Aside: empresa_id"| K_CAC
    E_USU -.->|"Chave Lógica: cpf (usuario_id)"| C_THR
    E_FRO -.->|"Chave Lógica: placa (placa_veiculo)"| C_THR
    E_VIA -.->|"Projeção de Malha: numero_gta + placa + cnh"| N_VIA
```

### 3.2 Mapeamento Conceitual de Entidades e Chaves de Integração entre Motores

Como bancos NoSQL, em memória e em grafos não compartilham restrições físicas de chave estrangeira com o motor relacional, a coesão semântica entre os quatro modelos é assegurada por **identificadores determinísticos de negócio e chaves universais**:

| Conceito de Domínio | PostgreSQL (Tabelas e Chaves) | Redis (Chaves e Estruturas) | MongoDB (Coleções e Campos) | Neo4j (Nós e Propriedades) |
| :--- | :--- | :--- | :--- | :--- |
| **Locatário / Empresa** | `sc_corporativo.tb_empresa` (`PK: id` UUID, `UK: cnpj`) | Prefixo de namespace `efficientia:{env}:{empresa_id}:*` | Isolamento por contexto de sessão do colaborador | Contexto corporativo das unidades frigoríficas |
| **Motorista / Usuário** | `sc_corporativo.tb_usuario` (`PK: id` UUID, `UK: cpf`, `UK: cnh`) | Membro `motorista_id` em ZSETs; sufixo em Hash `stats:motorista` e chave `ratelimit` | Campo `threads.usuario_id` (CPF) | Nó `(:Motorista)` (`UK: cnh`, `id`, `nome`, `categoria`) |
| **Frota (Cavalo e Carreta)** | `sc_frota.tb_veiculo_base` e filhas (`PK: id` UUID, `UK: placa`) | Atributos transportados no payload de eventos | Campo `threads.placa_veiculo` (`placa`) | Nó `(:Veiculo)` (`UK: placa`) e aresta `[:UTILIZOU_VEICULO {compartimento}]` |
| **Propriedade Rural** | `sc_corporativo.tb_fazenda` (`PK: id` UUID) | Atributo contextual de eventos operacionais | Contexto operacional nas consultas de diálogo | Nó `(:Fazenda)` (`UK: id`) conectado a `(:Pecuarista)` |
| **Unidade Frigorífica** | `sc_corporativo.tb_unidade_frigorifica` (`PK: id` UUID) | Membro `unidade_id` no ZSET `ranking:descarga:{data_iso}` | Contexto de destino nas interações | Nó `(:UnidadeFrigorifica)` (`UK: nome`, `capacidade_diaria`) |
| **Viagem / Transporte** | `sc_operacao.tb_relatorio_viagem` (`PK: id` UUID, `numero_gta`) | Evento no Stream `stream:eventos` (`relatorio_id`) | Diálogos de suporte durante o trânsito (`threads` / `messages`) | Nó `(:Viagem)` (`UK: numero_gta`, `data_embarque`, `qtd_morto`) |

---

## 4. Arquitetura Técnica e Fluxo de Funcionamento

O funcionamento integrado do ecossistema evita acoplamento síncrono bloqueante e elimina o problema de escrita dupla (*Dual-Write Problem*) por meio do padrão **Transactional Outbox** aliado à reconciliação periódica a partir da camada analítica.

```mermaid
sequenceDiagram
    autonumber
    participant App as Aplicativo / Sistema Operacional
    participant PG as PostgreSQL (Transacional + BI)
    participant Relay as Outbox Relay (Python)
    participant Redis as Redis (Streams, Cache e ZSET)
    participant Worker as Stream Consumer (Worker)
    participant Mongo as MongoDB (Orquestrador IA)
    participant Neo as Neo4j (Grafo Sanitário)

    App->>Redis: Verifica Rate Limit (INCR + TTL 60s) e lê SLA (Cache-Aside)
    Redis-->>App: Permissão concedida + Parâmetros operacionais
    App->>PG: INSERT/UPDATE em tb_relatorio_viagem (ou CALL sp_aprovar_relatorio)
    Note over PG: Trigger BEFORE valida CNH e inspeções. Trigger AFTER grava auditoria JSONB e insere tb_outbox_evento na mesma transação ACID
    loop Polling Assíncrono Não Bloqueante
        Relay->>PG: SELECT ... FROM tb_outbox_evento FOR UPDATE SKIP LOCKED
        Relay->>Redis: XADD efficientia:{env}:{empresa_id}:stream:eventos
        Relay->>PG: UPDATE tb_outbox_evento SET processado_em = NOW()
    end
    Worker->>Redis: XREADGROUP GROUP efficientia_event_consumers
    Note over Worker,Redis: Executa AlertaMortalidadeJob, AlertaEmergenciaJob e AtualizarRankingJob (HINCRBY + ZADD)
    Worker->>Redis: XACK (ou roteia para stream:dlq em caso de falha crítica)
    PG-->>Redis: Reconciliação periódica lê mv_analise_mortalidade_mensal e reconstrói ZSET/Hashes
    App->>Mongo: Registra sessão (threads) e mensagens/tool_calls (messages) com validação $jsonSchema
    PG-->>Neo: Projeção de GTAs, veículos e propriedades habilita Contact Tracing multissalto
```

### Síntese do Que Foi Construído em Cada Camada

1. **Núcleo Transacional e Analítico (`01_postgresql/`)**:
   * **Segregação Modular em 4 Schemas**: `sc_corporativo` (cadastros mestres e SLAs), `sc_frota` (herança de tabelas PostgreSQL `INHERITS` unificando cavalos mecânicos e carretas boiadeiras sob `tb_veiculo_base`), `sc_operacao` (relatórios de viagem, motivos de parada, anomalias de embarque/desembarque, parecer de análise e tabela Outbox) e `sc_auditoria` (catálogo ativo de dados com RBAC, trilha imutável de auditoria em JSONB e monitoramento DAU).
   * **Automação Transacional**: 4 funções PL/pgSQL, 6 triggers e 2 stored procedures que blindam o banco contra motoristas com CNH vencida ou veículos com inspeção expirada, mascaram automaticamente `senha_hash` nos logs de auditoria, garantem aprovação veterinária livre de condição de corrida (`FOR UPDATE`) e geram mensagens no Outbox atomicamente.
   * **Camada Analítica (*Star Schema*)**: 4 views de dimensão (incluindo polimorfismo via `tableoid` na dimensão de frota), 1 view de fato consolidando horas paradas, anomalias e quebra de inventário animal, e 1 *Materialized View* mensal com *Window Functions* (`SUM() OVER` acumulado no ano e `RANK() OVER` de mortalidade) preparada para atualização concorrente sem bloqueio de leitura (`REFRESH MATERIALIZED VIEW CONCURRENTLY`).
2. **Mensageria, Cache e Placares (`02_redis/`)**:
   * **9 Padrões de Chaves Multi-Tenant**: Governados centralmente pela classe `RedisKeys` com isolamento por ambiente (`{env}`) e empresa (`{empresa_id}`).
   * **Pipeline Orientado a Eventos**: Serviço `OutboxRelay` com busca concorrente `FOR UPDATE SKIP LOCKED`, consumidor `StreamConsumer` baseado em *Consumer Groups* com *Dead Letter Queue* (`stream:dlq`) automática, e 3 processadores especializados (`AlertaMortalidadeJob`, `AlertaEmergenciaJob` e `AtualizarRankingJob`).
   * **Placares Exatos, Reconciliação, Cache e Proteção**: Cálculo exato de taxa ponderada de mortalidade combinando contadores atômicos em `Hash` (`HINCRBY`) com ordenação $O(\log N)$ em `Sorted Sets` (`ZADD`), serviço `RankingReconciler` para reconstrução determinística via PostgreSQL, `ConfiguracaoCacheService` (*Cache-Aside* com TTL de 1 hora) e `RateLimiter` (*Fixed Window* de 60 segundos).
3. **Orquestração Conversacional de IA (`03_mongodb/`)**:
   * **Modelagem Híbrida Referenciada + Embutida**: Separação entre cabeçalho leve de sessão (`threads`) e histórico ilimitado de interações (`messages`) para evitar o limite de 16 MB por documento BSON e impedir reescrita de arrays crescentes, mantendo embutidos em cada mensagem os metadados de execução (`metadata`), as chamadas de ferramentas (`tool_calls`/`tool_outputs`) e a interpretação estruturada do agente (`json_orquestrador`).
   * **Rigor Estrutural e Observabilidade**: Validação ativa `strict` com `validationAction: "error"` via `$jsonSchema`, 7 índices especializados (evitando *in-memory sort* na montagem de contexto do LLM) e 4 consultas analíticas/operacionais cobrindo recuperação de prompt, junção `$lookup` da última mensagem, FinOps de tokens/latência e ranking de dúvidas da frota.
4. **Inteligência Epidemiológica em Grafo (`04_neo4j/`)**:
   * **Malha Logística como Grafo de Propriedades**: Representação de pecuaristas, fazendas, unidades frigoríficas, motoristas, veículos (cavalos e carretas desacopláveis) e viagens sanitárias (GTA).
   * **Rastreabilidade Sanitária Multissalto**: 6 restrições de unicidade, 3 índices secundários, carga realista com simulação de foco sanitário e transbordo interestadual de carreta contaminada, e 3 consultas Cypher avançadas (rastreamento temporal de contágio indireto, algoritmo `shortestPath` e grau de centralidade de super-disseminadores).

---

## 5. Especificação Técnica e Catálogo de Componentes

### 5.1 Matriz Comparativa dos Motores de Dados

| Motor | Paradigma | Responsabilidade Principal | Modelo de Consistência | Estruturas Dominantes | Artefatos no Repositório |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PostgreSQL** | Relacional e Objeto-Relacional | Fonte única da verdade (OLTP), auditoria, Outbox e Data Mart (OLAP) | Forte (ACID) | 4 Schemas, 17 Tabelas, 5 Views, 1 MV, 4 Functions, 6 Triggers, 2 Procedures | 21 scripts SQL + DBML + PDF |
| **Redis** | Chave-Valor e Estruturas em Memória | Fila de eventos, alertas operacionais, placares em tempo real, cache e *rate limit* | Atômica por comando / Eventual via Outbox e Reconciliação | 2 Streams, 3 Sorted Sets, 1 Hash, 3 Strings (Cache, Lock, Rate Limit) | CLI Python + 12 módulos `src/` + 5 suítes `tests/` |
| **MongoDB** | Orientado a Documentos (BSON) | Memória conversacional de IA, auditoria de *tool calls*, FinOps de LLM e intenções | Forte por documento + Validação estrita `$jsonSchema` | 2 Coleções (`threads`, `messages`), 7 Índices, 4 Consultas/Pipelines | 4 scripts JavaScript (`mongosh`) |
| **Neo4j** | Grafo de Propriedades (*Property Graph*) | Rastreamento epidemiológico (*Contact Tracing*), menor caminho e centralidade | Transacional em nós e arestas (*Index-Free Adjacency*) | 6 Rótulos de Nós, 5 Tipos de Relacionamentos, 6 Constraints, 3 Índices | 3 scripts Cypher (`.cypher`) |

### 5.2 Documentação Detalhada por Módulo

Cada subdiretório possui um documento técnico dedicado contendo dicionário completo de atributos, diagramas conceituais específicos do paradigma e instruções granulares de operação:

* [Documentação do Módulo PostgreSQL](./01_postgresql/README.md)
* [Documentação do Módulo Redis](./02_redis/README.md)
* [Documentação do Módulo MongoDB](./03_mongodb/README.md)
* [Documentação do Módulo Neo4j](./04_neo4j/README.md)

---

## 6. Requisitos e Configuração de Ambiente

### 6.1 Requisitos de Software

Para implantar e validar integralmente os quatro módulos em ambiente local ou servidor dedicado, são necessários os seguintes componentes:

* **PostgreSQL 15 ou superior**, acompanhado do cliente de linha de comando `psql` (ou cliente SQL compatível com execução sequencial de scripts UTF-8).
* **Redis 6.2 ou superior** (com suporte nativo a `Streams`, `Consumer Groups` e conexões TCP padrão `redis://` ou criptografadas com TLS `rediss://`).
* **MongoDB 6.0 ou superior**, acompanhado do shell interativo `mongosh` para execução dos scripts JavaScript.
* **Neo4j 5.0 ou superior**, acessível via `cypher-shell` ou interface gráfica Neo4j Browser.
* **Python 3.10 ou superior**, com `venv` e `pip` habilitados para execução dos trabalhadores assíncronos e da suíte de testes do módulo Redis.

### 6.2 Variáveis de Ambiente Padronizadas

Os diretórios `01_postgresql/` e `02_redis/` contêm arquivos `.env.example` que devem ser copiados para `.env` (ignorados pelo controle de versão) e preenchidos com as credenciais do servidor de destino:

| Variável | Módulo | Exemplo de Valor Padrão | Finalidade Técnica |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | PostgreSQL / Redis | `postgresql://usuario:senha@localhost:5432/efficientia` | URI padrão de conexão ao servidor PostgreSQL em modo de sessão direta |
| `REDIS_URL` | Redis | `redis://localhost:6379/0` ou `rediss://usuario:senha@servidor:6379` | URI de conexão ao servidor Redis (suporta conexões abertas ou sobre TLS) |
| `APP_ENV` | Redis | `development` | Identificador do ambiente (`development`, `staging`, `production`) usado no prefixo das chaves |
| `RELAY_POLL_INTERVAL_SECONDS` | Redis | `2.0` | Intervalo em segundos entre ciclos de leitura da tabela `tb_outbox_evento` |
| `RELAY_BATCH_SIZE` | Redis | `25` | Quantidade máxima de eventos capturados por lote transacional no Outbox |
| `WORKER_BLOCK_MS` | Redis | `5000` | Tempo máximo de espera bloqueante (ms) na chamada `XREADGROUP` |
| `MAX_JOB_RETRIES` | Redis | `3` | Limite de tentativas antes do encaminhamento do evento para a *Dead Letter Queue* |

---

## 7. Roteiro de Implantação e Execução

Execute as quatro etapas na ordem numérica abaixo para provisionar toda a arquitetura a partir do zero:

### Etapa 1: Provisionamento do Banco Relacional e Analítico (`01_postgresql/`)

```bash
# 1. Criação de schemas, tipos ENUM e tabelas
psql "$DATABASE_URL" -f 01_postgresql/01_ddl/01_schemas_e_tipos.sql
psql "$DATABASE_URL" -f 01_postgresql/01_ddl/02_catalogo_e_auditoria.sql
psql "$DATABASE_URL" -f 01_postgresql/01_ddl/03_corporativo_e_frota.sql
psql "$DATABASE_URL" -f 01_postgresql/01_ddl/04_tabelas_transacionais.sql

# 2. Criação de índices B-Tree e parciais
psql "$DATABASE_URL" -f 01_postgresql/02_constraints_and_indexes/01_keys_e_indexes.sql

# 3. Criação do Data Mart dimensional e Materialized View
psql "$DATABASE_URL" -f 01_postgresql/03_views/01_datamart_bi.sql

# 4. Compilação de funções, triggers e stored procedures
psql "$DATABASE_URL" -f 01_postgresql/04_functions/01_fn_registrar_auditoria.sql
psql "$DATABASE_URL" -f 01_postgresql/04_functions/02_fn_registrar_dau.sql
psql "$DATABASE_URL" -f 01_postgresql/04_functions/03_fn_validar_alocacao_viagem.sql
psql "$DATABASE_URL" -f 01_postgresql/04_functions/04_fn_gerar_outbox_relatorio.sql
psql "$DATABASE_URL" -f 01_postgresql/05_triggers/01_tg_auditoria.sql
psql "$DATABASE_URL" -f 01_postgresql/05_triggers/02_tg_validacoes_operacionais.sql
psql "$DATABASE_URL" -f 01_postgresql/06_procedures/01_sp_aprovar_relatorio.sql
psql "$DATABASE_URL" -f 01_postgresql/06_procedures/02_sp_registrar_anomalia.sql

# 5. Carga inicial de dados e atualização concorrente da Materialized View
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/01_carga_catalogo_dados.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/02_carga_corporativo.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/03_carga_frota_e_dominios.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/04_carga_relatorios_viagem.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/05_carga_paradas_e_anomalias.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/06_carga_auditoria_analise.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/07_carga_outbox_eventos.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/08_carga_monitoramento_dau.sql
psql "$DATABASE_URL" -c "REFRESH MATERIALIZED VIEW CONCURRENTLY sc_operacao.mv_analise_mortalidade_mensal;"
```

### Etapa 2: Inicialização da Mensageria, Workers e Testes (`02_redis/`)

```bash
cd 02_redis
python -m venv .venv
# No Windows (PowerShell): .\.venv\Scripts\Activate.ps1 | No Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

# Execução da suíte de testes offline em memória (fakeredis)
pytest -v

# Verificação de conectividade com PostgreSQL e Redis, Relay e Worker
python main.py check
python main.py relay --once
python main.py worker --once --consumer worker-01
python main.py reconcile
```

### Etapa 3: Inicialização do Banco Documental (`03_mongodb/`)

```bash
mongosh "mongodb://localhost:27017/efficientia_ai" 03_mongodb/01_schema_validation.js
mongosh "mongodb://localhost:27017/efficientia_ai" 03_mongodb/02_indexes.js
mongosh "mongodb://localhost:27017/efficientia_ai" 03_mongodb/03_seed_conversations.js
mongosh "mongodb://localhost:27017/efficientia_ai" 03_mongodb/04_conversational_queries.js
```

### Etapa 4: Inicialização do Banco em Grafo (`04_neo4j/`)

```bash
cypher-shell -u neo4j -p sua_senha -f 04_neo4j/01_schema_constraints.cypher
cypher-shell -u neo4j -p sua_senha -f 04_neo4j/02_seed_data.cypher
cypher-shell -u neo4j -p sua_senha -f 04_neo4j/03_traversal_queries.cypher
```

---

## 8. Governança, Concorrência, Segurança e Qualidade

* **Isolamento Multi-Tenant Nativo**: Todas as entidades corporativas, de frota e operacionais no PostgreSQL possuem chave estrangeira obrigatória `empresa_id` indexada por árvores B-Tree, e todas as chaves operacionais no Redis obedecem ao namespace `efficientia:{env}:{empresa_id}:*`, impedindo vazamento cruzado de informações entre transportadoras ou plantas industriais.
* **Controle de Concorrência sem Disputa Bloqueante**: A aprovação veterinária de relatórios aplica bloqueio pessimista de linha (`FOR UPDATE`) para evitar dupla aprovação simultânea, enquanto o `OutboxRelay` utiliza `FOR UPDATE SKIP LOCKED`, permitindo escalar múltiplos processos extratores em paralelo sem duplicidade de publicação no Redis.
* **Proteção de Credenciais e Auditoria Imutável**: As funções críticas de auditoria operam com `SECURITY DEFINER`, impedindo manipulação direta da tabela `sc_auditoria.tb_auditoria_log` por usuários comuns, e removem automaticamente o campo sensível `senha_hash` (`to_jsonb(...) - 'senha_hash'`) antes da gravação dos instantâneos JSONB.
* **Tolerância a Falhas e Autocorreção**: Mensagens com falha de processamento no consumidor Redis são isoladas em `stream:dlq` com rastreamento de grupo e identificador original, ao passo que eventuais divergências em memória são eliminadas pela rotina determinística `RankingReconciler` a partir da visão materializada do PostgreSQL.
* **Conformidade Sanitária e Regulatória**: A modelagem impõe integridade documental às Guias de Trânsito Animal (GTA), Notas Fiscais, validade de CNH, vencimento de inspeções de cavalos e carretas, laudos de mortalidade e rastreabilidade epidemiológica completa entre fazendas e unidades frigoríficas.
