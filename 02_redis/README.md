# Efficientia - Mensageria, Cache e Rankings em Tempo Real (Redis)

Módulo responsável pelo barramento assíncrono de eventos operacionais, processamento distribuído de filas com tolerância a falhas, placares competitivos em tempo real, cache de parâmetros de nível de serviço e limitação de taxa de requisições da plataforma **Efficientia**, implementado em **Python** sobre estruturas nativas em memória do **Redis**.

---

## 1. Visão Geral e Escopo Estratégico

No transporte pecuário de carga viva, eventos críticos — como a ocorrência de óbitos durante o percurso, a chegada de animais lesionados que exigem abate prioritário de emergência ou a aprovação veterinária de um lote desembarcado — demandam reação em milissegundos, sem onerar nem bloquear as transações principais do banco de dados relacional.

Para suprir essa camada de altíssima velocidade e desacoplamento temporal, o módulo `02_redis/` implementa cinco capacidades arquiteturais integradas:

1. **Retransmissão Transacional de Eventos (*Transactional Outbox Relay*)**: Extração contínua e não bloqueante de eventos gravados em `sc_operacao.tb_outbox_evento` no PostgreSQL (via `FOR UPDATE SKIP LOCKED`) e publicação ordenada em *Redis Streams* isolados por empresa.
2. **Consumo Distribuído Resiliente (*Consumer Groups* e *Dead Letter Queue*)**: Trabalhadores assíncronos concorrentes agrupados sob `efficientia_event_consumers` (`XREADGROUP`), com confirmação explícita de leitura (`XACK`) e roteamento automático de mensagens defeituosas para fila de isolamento (`stream:dlq`).
3. **Alertas Operacionais e Sanitários Instantâneos**: Processadores especializados que inspecionam cada evento publicado e disparam alertas imediatos de mortalidade animal (`AlertaMortalidadeJob`) e de prioridade de rampa/abate de emergência (`AlertaEmergenciaJob`).
4. **Placares Competitivos e Operacionais em Tempo Real (*Sorted Sets* + *Hashes*)**: Atualização incremental $O(\log N)$ de rankings mensais de motoristas (maior volume transportado e menor taxa ponderada de mortalidade) e eficiência diária de descarga das unidades frigoríficas, acompanhada de rotina de reconciliação determinística (`RankingReconciler`) a partir da *Materialized View* analítica do PostgreSQL.
5. **Cache de Baixa Latência e Proteção de Borda (*Cache-Aside* + *Rate Limiting*)**: Armazenamento temporário das metas operacionais e SLAs por empresa (`SETEX` com TTL de 1 hora) e controle de frequência de envio de relatórios por usuário via janela fixa atômica (`INCR` + `EXPIRE` de 60 segundos).

---

## 2. Estrutura Arquitetural de Diretórios

A arquitetura interna do módulo adota separação estrita de responsabilidades entre configuração, fábrica de chaves, conectividade, retransmissão, filas, processadores de negócio, placares, cache, interface de linha de comando e testes automatizados:

```text
02_redis/
├── .env.example                                  # Modelo de variáveis de ambiente para Redis e PostgreSQL
├── README.md                                     # Documentação completa das estruturas em memória e modelo conceitual
├── requirements.txt                              # Dependências do projeto (redis, psycopg, pydantic-settings, fakeredis, pytest)
├── main.py                                       # Interface de linha de comando (CLI) unificada com 7 subcomandos
│
├── config/                                       # Configurações de infraestrutura do servidor Redis
│   └── redis.conf                                # Diretivas de memória segura (noeviction), persistência AOF e rede
│
├── scripts/                                      # Scripts atômicos em linguagem Lua
│   ├── registrar_viagem_ranking.lua              # Atualização atômica combinada de hash de stats e sorted sets
│   └── verificar_rate_limit.lua                  # Algoritmo atômico de controle de taxa por janela temporal
│
├── src/                                          # Pacote principal de engenharia de dados em memória
│   ├── __init__.py                               # Inicializador do pacote raiz
│   ├── config.py                                 # Classe Settings com carregamento .env e validação de ambiente
│   ├── connection.py                             # Pool reutilizável Redis (TCP/TLS) e conexões PostgreSQL (dict_row)
│   ├── keys.py                                   # Classe RedisKeys centralizando os 9 padrões de chaves e Consumer Group
│   │
│   ├── cache/                                    # Submódulo de aceleração de leitura e proteção contra abuso
│   │   ├── __init__.py
│   │   ├── configuracao.py                       # ConfiguracaoCacheService (padrão Cache-Aside e invalidação explícita)
│   │   └── rate_limit.py                         # RateLimiter por usuário (algoritmo Fixed Window via pipeline atômico)
│   │
│   ├── jobs/                                     # Processadores modulares orientados a eventos (Padrão Strategy)
│   │   ├── __init__.py
│   │   ├── base.py                               # Interface abstrata BaseJob (can_handle e process)
│   │   ├── alerta_mortalidade.py                 # AlertaMortalidadeJob (detecção crítica de qtd_morto > 0)
│   │   ├── alerta_sla.py                         # AlertaEmergenciaJob (priorização de rampa quando qtd_emergencia > 0)
│   │   └── atualizar_ranking.py                  # AtualizarRankingJob (gatilho de placar em status_novo = 'aprovado')
│   │
│   ├── queues/                                   # Infraestrutura de consumo de Redis Streams
│   │   ├── __init__.py
│   │   └── consumer.py                           # StreamConsumer (XGROUP CREATE, XREADGROUP, XACK e envio para DLQ)
│   │
│   ├── ranking/                                  # Motor matemático de placares e consistência eventual
│   │   ├── __init__.py
│   │   ├── leaderboard.py                        # LeaderboardService (ZINCRBY, HINCRBY, ZADD, ZREVRANGE e ZRANGE)
│   │   └── reconciliacao.py                      # RankingReconciler (reconstrução em lote via mv_analise_mortalidade_mensal)
│   │
│   └── relay/                                    # Ponte assíncrona PostgreSQL -> Redis
│       ├── __init__.py
│       └── outbox_relay.py                       # OutboxRelay (polling transacional FOR UPDATE SKIP LOCKED + XADD)
│
└── tests/                                        # Suíte de testes unitários e integrados offline (fakeredis)
    ├── __init__.py
    ├── test_cache.py                             # Testes de Cache-Aside (hit/miss/invalidação) e RateLimiter
    ├── test_jobs.py                              # Testes unitários das regras de filtragem e disparo dos 3 Jobs
    ├── test_keys.py                              # Validação determinística da formatação dos namespaces multi-tenant
    ├── test_lua_and_config.py                    # Validação de integridade do redis.conf e scripts Lua atômicos
    ├── test_ranking.py                           # Validação matemática da taxa ponderada, ordenação e desempates
    └── test_stream.py                            # Testes integrados do ciclo XADD -> XREADGROUP -> Jobs -> XACK / DLQ
```

---

## 3. Modelo Conceitual

Em um banco de dados chave-valor e de estruturas em memória, o modelo conceitual expressa a **taxonomia hierárquica das chaves (*Keyspace*)**, o **tipo estrutural de cada valor armazenado** (`Stream`, `Sorted Set`, `Hash`, `String`), suas **propriedades internas** (campos de entrada, *members*, *scores*, contadores atômicos e políticas de expiração *TTL*) e os **relacionamentos funcionais de derivação e fluxo** entre essas estruturas.

### 3.1 Diagrama Conceitual de Chaves, Estruturas, Propriedades e Relações

```mermaid
erDiagram
    STREAM_EVENTOS ||--o{ STREAM_DLQ : "isola falhas de processamento"
    STREAM_EVENTOS ||--o{ HASH_STATS_MOTORISTA : "acumula contadores (HINCRBY)"
    STREAM_EVENTOS ||--o{ ZSET_RANKING_VOLUME : "incrementa volume (ZINCRBY)"
    HASH_STATS_MOTORISTA ||--|| ZSET_RANKING_MORTALIDADE : "pondera taxa exata (ZADD)"

    STREAM_EVENTOS {
        string chave PK "efficientia:{env}:{empresa_id}:stream:eventos"
        string consumer_group "efficientia_event_consumers"
        string entry_id "timestamp_ms-sequência"
        uuid evento_id FK "Referência lógica tb_outbox_evento.id"
        string agregado_tipo "relatorio_viagem"
        uuid agregado_id FK "Referência lógica tb_relatorio_viagem.id"
        string tipo_evento "relatorio.criado | relatorio.status_alterado"
        json payload "Dados operacionais e contagens animais"
        string ttl "Persistente até confirmação XACK"
    }

    STREAM_DLQ {
        string chave PK "efficientia:{env}:{empresa_id}:stream:dlq"
        string original_id "EntryID original no stream principal"
        string failed_at_group "efficientia_event_consumers"
        json payload "Cópia integral do evento para auditoria"
        string ttl "Persistente para reprocessamento"
    }

    HASH_STATS_MOTORISTA {
        string chave PK "efficientia:{env}:{empresa_id}:stats:motorista:{ano_mes}:{motorista_id}"
        int embarcados "Campo acumulado via HINCRBY"
        int mortos "Campo acumulado via HINCRBY"
        int viagens "Campo acumulado via HINCRBY"
        int ttl_segundos "7776000 (90 dias)"
    }

    ZSET_RANKING_VOLUME {
        string chave PK "efficientia:{env}:{empresa_id}:ranking:volume:{ano_mes}"
        uuid member FK "motorista_id"
        float score "Total de cabeças embarcadas (ZREVRANGE decrescente)"
        int ttl_segundos "7776000 (90 dias)"
    }

    ZSET_RANKING_MORTALIDADE {
        string chave PK "efficientia:{env}:{empresa_id}:ranking:mortalidade:{ano_mes}"
        uuid member FK "motorista_id"
        float score "Percentual ponderado mortos/embarcados*100 (ZRANGE crescente)"
        int ttl_segundos "7776000 (90 dias)"
    }

    ZSET_RANKING_DESCARGA {
        string chave PK "efficientia:{env}:{empresa_id}:ranking:descarga:{data_iso}"
        uuid member FK "unidade_id"
        float score "Tempo médio de descarga em horas (ZRANGE crescente)"
        int ttl_segundos "604800 (7 dias)"
    }

    STRING_CACHE_CONFIG {
        string chave PK "efficientia:{env}:{empresa_id}:config"
        float sla_horas_viagem_padrao "Propriedade JSON serializada"
        float sla_horas_alerta_descarga "Propriedade JSON serializada"
        float meta_max_mortalidade_perc "Propriedade JSON serializada"
        int intervalo_alerta_parada_min "Propriedade JSON serializada"
        int ttl_segundos "3600 (1 hora - Cache-Aside)"
    }

    STRING_RATE_LIMIT {
        string chave PK "efficientia:{env}:ratelimit:report:{usuario_id}"
        int contador "Requisições acumuladas via INCR (limite padrão: 20)"
        int ttl_segundos "60 (Fixed Window)"
    }

    STRING_LOCK_DISTRIBUIDO {
        string chave PK "efficientia:{env}:{empresa_id}:lock:{job_key}"
        string token_detentor "Identificador de exclusão mútua"
        int ttl_segundos "Expiração preventiva contra deadlock"
    }
```

### 3.2 Hierarquia Conceitual do Espaço de Chaves (*Keyspace Multi-Tenant*)

Toda chave gerada pela classe `RedisKeys` (`src/keys.py`) segue convenção determinística delimitada por dois-pontos (`:`), isolando tanto o ambiente de implantação (`development`, `staging`, `production`) quanto a empresa locatária (`{empresa_id}`):

```mermaid
flowchart LR
    ROOT["efficientia"] --> ENV["{env}"]
    ENV --> TENANT["{empresa_id}"]
    ENV --> RL["ratelimit:report:{usuario_id} (String Int | TTL 60s)"]

    TENANT --> STR_EV["stream:eventos (Stream Principal)"]
    TENANT --> STR_DLQ["stream:dlq (Stream Dead Letter Queue)"]
    TENANT --> CFG["config (String JSON | TTL 1h)"]
    TENANT --> LCK["lock:{job_key} (String Trava Distribuída)"]
    TENANT --> HSH["stats:motorista:{ano_mes}:{motorista_id} (Hash | TTL 90d)"]
    TENANT --> RK_VOL["ranking:volume:{ano_mes} (Sorted Set | TTL 90d)"]
    TENANT --> RK_MOR["ranking:mortalidade:{ano_mes} (Sorted Set | TTL 90d)"]
    TENANT --> RK_DES["ranking:descarga:{data_iso} (Sorted Set | TTL 7d)"]
```

---

## 4. Arquitetura Técnica e Fluxo de Funcionamento

O pipeline assíncrono foi projetado para garantir semântica de entrega *At-Least-Once* (pelo menos uma vez) na fila de eventos, combinada à autocorreção periódica de estado analítico.

```mermaid
flowchart TD
    PG_OUT["PostgreSQL: sc_operacao.tb_outbox_evento (processado_em IS NULL)"]
    RELAY["OutboxRelay (SELECT ... FOR UPDATE SKIP LOCKED)"]
    STREAM["Redis Stream: efficientia:{env}:{empresa_id}:stream:eventos"]
    CG["StreamConsumer: Group efficientia_event_consumers (XREADGROUP BLOCK 5000ms)"]

    J1["AlertaMortalidadeJob (qtd_morto > 0)"]
    J2["AlertaEmergenciaJob (qtd_emergencia > 0)"]
    J3["AtualizarRankingJob (status_novo == 'aprovado')"]

    ACK["Confirmação XACK (Remove da Pending Entries List)"]
    DLQ["Isolamento em stream:dlq + XACK no stream principal"]

    LB["LeaderboardService (Pipeline: ZINCRBY + HINCRBY + EXPIRE + ZADD)"]
    PG_MV["PostgreSQL: sc_operacao.mv_analise_mortalidade_mensal"]
    REC["RankingReconciler (DELETE + Pipeline Rebuild)"]

    PG_OUT -->|"Lote de 25 registros"| RELAY
    RELAY -->|"XADD e UPDATE processado_em"| STREAM
    STREAM --> CG
    CG --> J1 & J2 & J3
    J3 --> LB
    J1 & J2 & LB -->|"Sucesso"| ACK
    CG -.->|"Exceção ou falha"| DLQ
    PG_MV -.->|"Fonte da Verdade Mensal"| REC
    REC -.->|"Sincroniza Hashes e ZSETs"| LB
```

### Detalhamento dos Mecanismos Construídos

1. **Extração Concorrente sem Duplicidade (`OutboxRelay`)**:
   * Conecta-se ao PostgreSQL com `autocommit=False` e fábrica `dict_row`, buscando lotes ordenados por `criado_em ASC` onde `processado_em IS NULL` e `erro_tentativas < MAX_JOB_RETRIES` (padrão `3`).
   * A cláusula `FOR UPDATE SKIP LOCKED` permite que múltiplas instâncias do `OutboxRelay` operem simultaneamente sobre a tabela `tb_outbox_evento` sem bloqueio mútuo e sem publicar o mesmo evento duas vezes.
   * Após publicar via `XADD` no stream da respectiva `empresa_id`, grava `processado_em = NOW()`. Caso ocorra falha de rede no Redis, incrementa `erro_tentativas` e registra a rastreabilidade diagnóstica em `ultimo_erro`.
2. **Consumo Distribuído e *Dead Letter Queue* (`StreamConsumer`)**:
   * Na inicialização (`ensure_group`), executa `XGROUP CREATE <stream> efficientia_event_consumers 0 MKSTREAM`, tratando de forma idempotente o retorno `BUSYGROUP` caso o grupo já exista.
   * Consome mensagens novas (`>`) via `XREADGROUP` com espera bloqueante configurável (`WORKER_BLOCK_MS=5000`), evitando *busy-waiting* de CPU quando a fila está ociosa.
   * Submete o payload desserializado aos processadores filhos de `BaseJob`. Se todos os jobs aplicáveis retornarem êxito, emite `XACK`. Caso qualquer processador retorne falha ou lance exceção não tratada, copia integralmente o evento enriquecido com `original_id` e `failed_at_group` para `stream:dlq` e emite `XACK` no stream principal para não travar a fila.
3. **Cálculo Matemático Exato em Placares Ponderados (`LeaderboardService`)**:
   * Somar ou tirar média aritmética simples de percentuais de viagens individuais produziria distorção estatística entre lotes de tamanhos distintos (ex.: 1 óbito em 10 animais = 10% contra 0 óbito em 90 animais = 0% resulta em 1% real em 100 animais, e não 5%).
   * Para resolver esse problema em tempo real, `registrar_viagem_aprovada` executa um `pipeline` atômico que acumula `embarcados`, `mortos` e `viagens` via `HINCRBY` no Hash `stats:motorista`, incrementa o volume no ZSET `ranking:volume` via `ZINCRBY` e, em seguida, calcula a razão exata $\text{taxa} = \text{round}\left(\frac{\text{mortos}}{\text{embarcados}} \times 100, 4\right)$ gravando o *score* atualizado via `ZADD` em `ranking:mortalidade`.
4. **Reconciliação Determinística (`RankingReconciler`)**:
   * Lê os indicadores consolidados de `sc_operacao.mv_analise_mortalidade_mensal` no PostgreSQL (com filtro opcional por `ano_mes_embarque`), agrupa os registros por `(empresa_id, ano_mes)`, limpa os conjuntos anteriores e reconstrói integralmente os `Sorted Sets` e `Hashes` em um único `pipeline` transacional, garantindo convergência absoluta entre memória e disco.
5. **Padrão *Cache-Aside* (`ConfiguracaoCacheService`) e *Rate Limiting* (`RateLimiter`)**:
   * `obter_configuracao(empresa_id)` prioriza leitura em memória (`GET`); apenas em caso de *Cache Miss* consulta `sc_corporativo.tb_configuracao_operacao` no PostgreSQL e armazena o JSON via `SETEX` por `3600` segundos. Oferece `invalidar(empresa_id)` para limpeza imediata após alterações administrativas de SLA.
   * `verificar_permissao(usuario_id)` protege a API de submissão de relatórios contra rajadas excessivas ou loops acidentais em dispositivos móveis, limitando por padrão a `20` envios por janela de `60` segundos por colaborador.

---

## 5. Especificação Técnica e Catálogo de Componentes

### 5.1 Dicionário Completo dos 9 Padrões de Chaves (`src/keys.py`)

| Padrão de Chave | Estrutura Redis | Membros / Campos / Valor | Comandos Principais | Política de TTL |
| :--- | :--- | :--- | :--- | :--- |
| `efficientia:{env}:{empresa_id}:stream:eventos` | `Stream` | Campos: `evento_id`, `agregado_tipo`, `agregado_id`, `tipo_evento`, `payload`, `criado_em` | `XADD`, `XGROUP CREATE`, `XREADGROUP`, `XACK` | Retenção controlada por consumo |
| `efficientia:{env}:{empresa_id}:stream:dlq` | `Stream` | Campos originais + `original_id`, `failed_at_group` | `XADD`, `XRANGE` | Persistente (auditoria operacional) |
| `efficientia:{env}:{empresa_id}:ranking:volume:{ano_mes}` | `Sorted Set` | `Member`: `motorista_id` \| `Score`: total de animais embarcados | `ZINCRBY`, `ZADD`, `ZREVRANGE`, `EXPIRE` | 90 dias (`7.776.000s`) |
| `efficientia:{env}:{empresa_id}:ranking:mortalidade:{ano_mes}` | `Sorted Set` | `Member`: `motorista_id` \| `Score`: percentual ponderado de mortalidade | `ZADD`, `ZRANGE`, `EXPIRE` | 90 dias (`7.776.000s`) |
| `efficientia:{env}:{empresa_id}:ranking:descarga:{data_iso}` | `Sorted Set` | `Member`: `unidade_id` \| `Score`: horas médias de desembarque | `ZADD`, `ZRANGE`, `EXPIRE` | 7 dias (`604.800s`) |
| `efficientia:{env}:{empresa_id}:stats:motorista:{ano_mes}:{motorista_id}` | `Hash` | Campos inteiros: `embarcados`, `mortos`, `viagens` | `HINCRBY`, `HSET`, `HGETALL`, `EXPIRE` | 90 dias (`7.776.000s`) |
| `efficientia:{env}:{empresa_id}:config` | `String` (JSON) | JSON serializado de `tb_configuracao_operacao` | `GET`, `SETEX`, `DELETE` | 1 hora (`3.600s`) |
| `efficientia:{env}:{empresa_id}:lock:{job_key}` | `String` | Token de exclusão mútua distribuída para tarefas concorrentes | `SET NX EX`, `DEL` | Definido por operação |
| `efficientia:{env}:ratelimit:report:{usuario_id}` | `String` (Int) | Contador inteiro de requisições na janela vigente | `INCR`, `TTL`, `EXPIRE` | 60 segundos (`Fixed Window`) |

### 5.2 Catálogo de Subcomandos da CLI (`main.py`)

| Subcomando | Parâmetros Suportados | Descrição Operacional |
| :--- | :--- | :--- |
| `check` | *(nenhum)* | Executa `PING` no Redis e `SELECT 1` no PostgreSQL, exibindo diagnóstico imediato de conectividade |
| `relay` | `--once` | Inicia o `OutboxRelay` em laço contínuo (ou executa apenas um lote único quando `--once` é informado) |
| `worker` | `--empresa <UUID>`, `--consumer <ID>`, `--once` | Inicia o `StreamConsumer` escutando o stream da empresa informada e processando os 3 *Jobs* |
| `test-event` | `--empresa <UUID>`, `--mortos <INT>`, `--usuario <ID>` | Valida o *Rate Limiter* e injeta diretamente um evento sintético de aprovação no stream para testes |
| `ranking` | `--empresa <UUID>`, `--mes <YYYY-MM>` | Consulta e imprime no console o Top 10 de volume e o Top 10 de menor mortalidade do mês |
| `reconcile` | `--mes <YYYY-MM>` | Executa `RankingReconciler` sincronizando os placares do Redis com `mv_analise_mortalidade_mensal` |
| `cache-config` | `--empresa <UUID>` | Testa o ciclo de *Cache-Aside* (leitura do PostgreSQL na primeira chamada e *Cache Hit* nas seguintes) |

### 5.3 Suíte de Testes Automatizados (`tests/`)

| Arquivo de Teste | Escopo Verificado |
| :--- | :--- |
| `tests/test_keys.py` | Formatação exata dos namespaces, isolamento de `empresa_id` e unicidade semântica dos 9 padrões de chaves |
| `tests/test_cache.py` | Fluxo completo de *Cache Miss*, *Cache Hit*, invalidação explícita de configuração e bloqueio da 21ª requisição no `RateLimiter` |
| `tests/test_jobs.py` | Seletividade `can_handle` e lógica de negócio de `AlertaMortalidadeJob`, `AlertaEmergenciaJob` e `AtualizarRankingJob` |
| `tests/test_ranking.py` | Precisão aritmética da mortalidade acumulada em múltiplas viagens, ordenação crescente/decrescente e TTLs |
| `tests/test_stream.py` | Ciclo ponta a ponta com `fakeredis`: `XADD`, criação idempotente de grupo, `XREADGROUP`, `XACK` e desvio para `stream:dlq` |

---

## 6. Requisitos e Configuração de Ambiente

### 6.1 Pré-Requisitos

* **Python 3.10 ou superior** com suporte a `venv` e `pip`.
* **Servidor Redis 6.2 ou superior** (compatível tanto com protocolo padrão `redis://` quanto com conexões criptografadas via TLS `rediss://`).
* **Servidor PostgreSQL 15 ou superior** inicializado com o esquema do diretório `01_postgresql/` (necessário para os comandos `check`, `relay`, `reconcile` e *fallback* de `cache-config`; dispensável para a execução dos testes unitários com `pytest`).

### 6.2 Variáveis de Ambiente (`.env`)

Copie o arquivo `.env.example` para `.env` na pasta `02_redis/` e ajuste os parâmetros conforme o ambiente de execução:

```ini
APP_ENV=development

# URI de conexão com o servidor Redis (redis:// para TCP local ou rediss:// para TLS)
REDIS_URL=redis://localhost:6379/0

# URI de conexão com o servidor PostgreSQL em modo de sessão direta
DATABASE_URL=postgresql://postgres:sua_senha_segura@localhost:5432/efficientia

# Parâmetros operacionais de vazão, espera bloqueante e retentativas
RELAY_POLL_INTERVAL_SECONDS=2.0
RELAY_BATCH_SIZE=25
WORKER_BLOCK_MS=5000
MAX_JOB_RETRIES=3
```

---

## 7. Roteiro de Implantação e Execução

### 7.1 Instalação do Ambiente Virtual e Execução dos Testes Offline

```bash
cd 02_redis

# Criação e ativação do ambiente virtual Python
python -m venv .venv
# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# Instalação das dependências
pip install -r requirements.txt

# Execução completa dos testes automatizados em memória (não requer servidor Redis externo)
pytest -v
```

### 7.2 Operação Integrada via Linha de Comando (`main.py`)

```bash
# 1. Validar conectividade ativa com Redis e PostgreSQL
python main.py check

# 2. Publicar um lote pendente da tabela tb_outbox_evento para os Redis Streams
python main.py relay --once

# 3. Iniciar trabalhador contínuo em segundo plano para uma empresa específica
python main.py worker --empresa c6aa229c-2c1d-56de-a6ea-280b898b0a7e --consumer worker-01

# 4. Simular publicação direta de evento aprovado com 1 óbito e consumir em ciclo único
python main.py test-event --empresa c6aa229c-2c1d-56de-a6ea-280b898b0a7e --mortos 1 --usuario mot-001
python main.py worker --empresa c6aa229c-2c1d-56de-a6ea-280b898b0a7e --once

# 5. Inspecionar placares em tempo real e reconciliar com a Materialized View do PostgreSQL
python main.py ranking --empresa c6aa229c-2c1d-56de-a6ea-280b898b0a7e --mes 2026-10
python main.py reconcile --mes 2026-10

# 6. Verificar leitura e escrita de SLAs operacionais em cache
python main.py cache-config --empresa c6aa229c-2c1d-56de-a6ea-280b898b0a7e
```

---

## 8. Governança, Concorrência, Segurança e Qualidade

* **Pool de Conexões Reutilizável e Suporte a TLS**: O módulo `src/connection.py` gerencia um `redis.ConnectionPool` global configurado com `decode_responses=True`, `socket_timeout=10`, `socket_connect_timeout=10` e `retry_on_timeout=True`, negociando criptografia em trânsito automaticamente sempre que o esquema `rediss://` é utilizado.
* **Trava de Segurança para Ambiente Produtivo**: O método `Settings.validate()` bloqueia a subida de serviços em `APP_ENV=production` caso `REDIS_URL` aponte acidentalmente para `localhost` ou esteja ausente.
* **Prevenção de *Poison Pill* em Filas**: Eventos corrompidos ou que provoquem falha lógica em processadores não bloqueiam indefinidamente o *Consumer Group*, sendo transferidos atomicamente para `stream:dlq` com preservação integral dos campos originais para reprocessamento auditado.
* **Gestão Automática de Memória (Políticas de Expiração)**: Todas as estruturas voláteis e analíticas temporais recebem `EXPIRE` explícito via `pipeline` (60s para *Rate Limit*, 1h para cache de SLA, 7 dias para eficiência diária de descarga e 90 dias para estatísticas e rankings mensais), prevenindo crescimento descontrolado de memória RAM.
* **Verificação Determinística sem Dependências de Rede**: A suíte `pytest` utiliza `fakeredis` para emular fielmente Streams, Consumer Groups, Sorted Sets, Hashes e TTLs em memória local, garantindo validação rápida e reprodutível em qualquer ambiente de integração contínua.
