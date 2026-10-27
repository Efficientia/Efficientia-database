# Efficientia - Sistema de Filas, Mensageria e Rankings em Tempo Real (Redis / Upstash)

Este diretório contém a camada de processamento assíncrono orientada a eventos, mensageria confiável e computação de rankings em tempo real do ecossistema **Efficientia**, utilizando **Redis Streams**, **Sorted Sets (ZSET)**, **Hashes (HSET)** e integração transacional com PostgreSQL via **Transactional Outbox**.

---

## 1. Visão Geral e Escopo Técnico

No transporte de animais vivos, a ocorrência de atrasos, temperaturas adversas ou mortalidade exige notificações imediatas e cálculo de indicadores de qualidade operacional sem degradar o banco transacional principal.

O módulo baseado em Redis / Upstash desempenha as seguintes funções:

* **Desacoplamento Assíncrono**: O banco relacional registra a mudança de estado e o evento transactional outbox de forma atômica; o componente de mensageria processa eventos sem impactar a latência das transações de negócio.
* **Consumo Concorrente com Consumer Groups**: Eventos são distribuídos entre múltiplos workers sem risco de duplicação, com confirmação explícita (*XACK*) e tratamento de mensagens pendentes (*PEL - Pending Entries List*).
* **Placares e Rankings em Memória (Sorted Sets)**: Computação em tempo real de motoristas de destaque por volume transportado e menor taxa de mortalidade, com complexidade algorítmica $O(\log N)$.
* **Resiliência e Dead Letter Queue (DLQ)**: Falhas transientes acionam retentativas; falhas definitivas são desviadas para uma stream de auditoria sem bloquear a fila principal.

---

## 2. Estrutura Estratégica de Diretórios

A arquitetura do módulo é estruturada em camadas de serviço, mensageria, persistência em memória e testes:

```text
02_redis/
├── .env.example                     # Configurações de conexão Redis/Upstash (TLS) e PostgreSQL
├── README.md                        # Documentação técnica e guia operacional do módulo Redis
├── requirements.txt                 # Dependências do driver redis-py, psycopg e framework de testes
├── main.py                          # CLI unificada de gerenciamento de relays, workers e rankings
│
├── src/                             # Código-fonte do módulo
│   ├── config.py                    # Carregamento centralizado de variáveis de ambiente
│   ├── connection.py                # Fábricas de conexão para Redis e PostgreSQL com pooling
│   ├── keys.py                      # Padronização semântica e namespace de chaves Redis
│   │
│   ├── cache/                       # Camada de Cache em Memória
│   │   ├── configuracao.py          # Cache-Aside de parâmetros operacionais da empresa
│   │   └── rate_limit.py            # Rate Limiter atômico com comandos INCR e EXPIRE
│   │
│   ├── jobs/                        # Processadores de Regra de Negócio
│   │   ├── base.py                  # Classe abstrata para definição de jobs assíncronos
│   │   ├── alerta_mortalidade.py    # Disparo de alertas críticos para casos de óbito no trajeto
│   │   ├── alerta_sla.py            # Notificação de estouro de SLA de tempo de viagem
│   │   └── atualizar_ranking.py     # Atualização incremental de placares em Sorted Sets
│   │
│   ├── queues/                      # Gestão de Filas e Streams
│   │   └── consumer.py              # Leitura de Consumer Groups com XREADGROUP e controle de DLQ
│   │
│   ├── ranking/                     # Gestão de Placares
│   │   ├── leaderboard.py           # Consultas e ordenação de placares mensais
│   │   └── reconciliacao.py         # Sincronização de placares a partir de Materialized Views
│   │
│   └── relay/                       # Integração Transacional
│       └── outbox_relay.py          # Leitura de tb_outbox_evento com locks e publicação (XADD)
│
└── tests/                           # Suíte de Testes Automatizados
    ├── test_cache.py                # Validação de estratégias de Cache-Aside e Rate Limiting
    ├── test_jobs.py                 # Testes unitários para os jobs de alerta e atualização
    ├── test_keys.py                 # Validação de máscaras e padrões de namespace de chaves
    ├── test_ranking.py              # Testes de pontuação e desempate em Sorted Sets
    └── test_stream.py               # Testes de fluxo de streams, Consumer Groups e DLQ com fakeredis
```

---

## 3. Decisões Arquiteturais e Topologia de Eventos

A solução adota o padrão **Transactional Outbox Relay** para transferir eventos do PostgreSQL para o Redis Streams de maneira confiável:

```mermaid
flowchart TD
    subgraph PostgreSQL ["PostgreSQL / Supabase"]
        A["tb_relatorio_viagem"] -->|"Trigger ACID"| B["tb_outbox_evento"]
        B -->|"FOR UPDATE SKIP LOCKED"| C["Outbox Relay"]
        M["mv_analise_mortalidade_mensal"] -.->|"Reconciliação Analítica"| R["Leaderboard (Sorted Sets)"]
    end

    subgraph Redis_Streams ["Redis / Upstash (Streams)"]
        C -->|"XADD (TLS rediss://)"| D["Stream de Eventos"]
        D -->|"XREADGROUP"| E["Consumer Group Worker"]
        E -->|"Falha Definitiva"| F["Dead Letter Queue (stream:dlq)"]
        E -->|"Sucesso"| G["XACK"]
    end

    subgraph Jobs_Processamento ["Processamento de Jobs"]
        E --> H["AlertaMortalidadeJob"]
        E --> I["AlertaSLAJob"]
        E --> J["AtualizarRankingJob"]
        J --> R
        J --> S["Stats Motorista (Hashes)"]
    end
```

---

## 4. Dicionário de Estruturas de Dados e Padrão de Chaves

Todas as chaves seguem uma nomenclatura semântica com namespace para suportar ambientes multi-tenant e prevenção de colisões:

| Recurso | Tipo Redis | Padrão da Chave | Complexidade | Finalidade Operacional |
| :--- | :--- | :--- | :--- | :--- |
| **Stream de Eventos** | Stream | `efficientia:{env}:{empresa}:stream:eventos` | $O(1)$ inserção | Ingestão ordenada de eventos transacionais da empresa |
| **Dead Letter Queue** | Stream | `efficientia:{env}:{empresa}:stream:dlq` | $O(1)$ inserção | Isolamento de mensagens corrompidas ou irrecuperáveis |
| **Ranking Volume** | Sorted Set | `efficientia:{env}:{empresa}:ranking:volume:{ano_mes}` | $O(\log N)$ | Placar cumulativo de animais transportados no período |
| **Ranking Mortalidade** | Sorted Set | `efficientia:{env}:{empresa}:ranking:mortalidade:{ano_mes}` | $O(\log N)$ | Taxa percentual ponderada de mortalidade no mês |
| **Estatísticas do Motorista** | Hash | `efficientia:{env}:{empresa}:stats:motorista:{ano_mes}:{id}` | $O(1)$ | Contadores atômicos de viagens, cabeças e ocorrências |
| **Cache de Parâmetros** | String / JSON | `efficientia:{env}:{empresa}:config` | $O(1)$ | Cache-Aside de parâmetros de operação e tolerância de SLA |
| **Limitador de Requisições** | String / Int | `efficientia:{env}:ratelimit:report:{id}` | $O(1)$ | Rate limiter atômico com janelas deslizantes via EXPIRE |

---

## 5. Instalação, Dependências e Configuração de Ambiente

### 1. Criar e Ativar Ambiente Virtual Python

```bash
# Criar o ambiente virtual:
python -m venv .venv

# No Windows (PowerShell):
.venv\Scripts\Activate.ps1

# No Linux / macOS:
source .venv/bin/activate
```

### 2. Instalar Dependências

```bash
pip install -r 02_redis/requirements.txt
```

### 3. Configurar Variáveis de Ambiente

Copie o arquivo `.env.example` para `.env` no diretório do módulo ou na raiz:

```bash
cp 02_redis/.env.example 02_redis/.env
```

Preencha as variáveis com as credenciais apropriadas:
* `REDIS_URL`: Endereço de conexão compatível com Upstash ou Redis local (exemplo: `rediss://default:TOKEN@INSTANCIA.upstash.io:6379`).
* `DATABASE_URL`: String de conexão do PostgreSQL utilizando a porta de conexão direta (porta 5432).
* `ENVIRONMENT`: Identificador de ambiente (`development`, `staging`, `production`).

---

## 6. Roteiro Operacional e Comandos da CLI

A CLI operacional é centralizada por meio do ponto de entrada `02_redis/main.py`:

### 1. Validar Conectividade com os Bancos
Testa conexões ativas com a instância do Redis e a base do PostgreSQL:
```bash
python 02_redis/main.py check
```

### 2. Executar o Outbox Relay
Inicia a rotina de polling que lê eventos de `sc_operacao.tb_outbox_evento` e publica no Redis Stream da respectiva empresa:
```bash
python 02_redis/main.py relay
```

### 3. Iniciar um Worker de Filas para uma Empresa
Instancia o consumidor que processa eventos da stream, dispara alertas e atualiza os placares:
```bash
python 02_redis/main.py worker --empresa <UUID_DA_EMPRESA>
```

### 4. Consultar os Rankings em Tempo Real
Exibe os condutores com maior volume de carga e com menor índice de mortalidade no período corrente:
```bash
python 02_redis/main.py ranking --empresa <UUID_DA_EMPRESA>
```

### 5. Reconciliar Placares a partir da Camada Analítica
Reidrata os Sorted Sets do Redis a partir dos dados consolidados na Materialized View do PostgreSQL (`mv_analise_mortalidade_mensal`):
```bash
python 02_redis/main.py reconcile --empresa <UUID_DA_EMPRESA>
```

### 6. Consultar e Aquecer Cache de Parâmetros Operacionais
```bash
python 02_redis/main.py cache-config --empresa <UUID_DA_EMPRESA>
```

---

## 7. Resiliência, Dead Letter Queue e Testes Automatizados

### Tratamento de Falhas e Dead Letter Queue (DLQ)
Quando um evento processado por um worker lança uma exceção não recuperável (dados incongruentes ou falhas persistentes), a mensagem é direcionada à stream `stream:dlq` com os metadados de erro, liberando a fila principal via `XACK` para evitar bloqueios de fila (*Head-of-Line Blocking*).

### Suíte de Testes em Memória (Fakeredis)
Os testes automatizados utilizam a biblioteca `fakeredis`, permitindo a validação completa de pipelines, Consumer Groups e Sorted Sets sem conexão ativa com a internet e sem consumo de cotas de provedores em nuvem:

```bash
# Execução via módulo unittest padrão:
python -m unittest discover -s 02_redis/tests

# Execução via pytest:
pytest 02_redis/tests/
```
