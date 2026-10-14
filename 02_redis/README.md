# Sistema de Filas, Mensageria e Rankings em Tempo Real com Redis (Upstash)

Este diretório contém a implementação da camada de mensageria assíncrona, filas de processamento e rankings em tempo real do ecossistema **Efficientia**, utilizando **Redis Streams**, **Sorted Sets (ZSET)**, **Hashes (HSET)** e integração ao PostgreSQL via **Transactional Outbox**.

---

## 🏗️ Arquitetura do Sistema

```text
[ Supabase / PostgreSQL ]
   │
   ├─► tb_relatorio_viagem (INSERT / UPDATE status)
   │      │
   │      ▼ (Trigger síncrono ACID)
   ├─► tb_outbox_evento
   │      │
   │      ▼ (Polling assíncrono via FOR UPDATE SKIP LOCKED)
   │ [ Outbox Relay Python ]
   │      │
   │      ▼ (XADD com suporte a TLS rediss://)
   └─► [ Upstash / Redis Streams ] (efficientia:env:empresa_id:stream:eventos)
          │
          ▼ (XREADGROUP com BLOCK para economia de quota)
       [ Stream Consumer Workers ]
          │
          ├─► Job: AlertaMortalidadeJob (Detecção de óbitos / Laudo SIF)
          ├─► Job: AlertaEmergenciaJob (Animais fadigados / Curral prioritário)
          ├─► Job: AtualizarRankingJob ──► [ Redis Sorted Sets & Hashes ]
          │                                  ├─► ranking:volume:{ano_mes} (ZINCRBY)
          │                                  ├─► stats:motorista:{ano_mes} (HINCRBY)
          │                                  └─► ranking:mortalidade:{ano_mes} (ZADD)
          │
          ├─► Sucesso: XACK
          └─► Falha: Encaminhamento para Dead Letter Queue (stream:dlq)

[ Reconciliação Analítica ]:
   PostgreSQL (sc_operacao.mv_analise_mortalidade_mensal) ──► Re-hidratação dos Sorted Sets no Redis
```

---

## 📊 Estruturas de Dados no Redis

| Recurso | Tipo Redis | Padrão da Chave | Complexidade | Propósito |
|---|---|---|---|---|
| **Fila de Eventos** | Stream | `efficientia:{env}:{empresa}:stream:eventos` | O(1) / O(N) | Fila transacional com Consumer Groups |
| **Dead Letter Queue** | Stream | `efficientia:{env}:{empresa}:stream:dlq` | O(1) | Armazena eventos com falhas de processamento |
| **Ranking Volume** | Sorted Set | `efficientia:{env}:{empresa}:ranking:volume:{mes}` | O(log N) | Total de animais transportados por condutor |
| **Ranking Mortalidade**| Sorted Set | `efficientia:{env}:{empresa}:ranking:mortalidade:{mes}` | O(log N) | Taxa percentual de mortes ponderada no mês |
| **Stats Motorista** | Hash | `efficientia:{env}:{empresa}:stats:motorista:{mes}:{id}` | O(1) | Contadores de viagens, cabeças e óbitos |
| **Cache de Parâmetros**| String/JSON | `efficientia:{env}:{empresa}:config` | O(1) | Cache-Aside de `tb_configuracao_operacao` |
| **Rate Limiter** | String/Int | `efficientia:{env}:ratelimit:report:{id}` | O(1) | Controle atômico com INCR + EXPIRE |

---

## 📦 Instalação e Configuração

### 1. Criar ambiente virtual Python
```bash
python -m venv .venv

# No Windows (PowerShell):
.venv\Scripts\Activate.ps1

# No Linux / macOS:
source .venv/bin/activate
```

### 2. Instalar dependências
```bash
pip install -r 02_redis/requirements.txt
```

### 3. Configurar variáveis de ambiente
Copie o arquivo `.env.example` para `.env` dentro de `02_redis/` ou na raiz do repositório:
```bash
cp 02_redis/.env.example 02_redis/.env
```
Preencha a variável `REDIS_URL` com as credenciais do seu banco Upstash (ex: `rediss://default:...@...upstash.io:6379`) e a `DATABASE_URL` com os dados de conexão do Supabase (porta 5432).

---

## 🚀 Como Executar (CLI Centralizada)

A CLI está disponível através do arquivo `02_redis/main.py`:

### 1. Testar conectividade com os bancos
```bash
python 02_redis/main.py check
```

### 2. Iniciar o Outbox Relay
Lê eventos gerados pelas triggers do PostgreSQL e publica no Redis:
```bash
python 02_redis/main.py relay
```

### 3. Iniciar um Worker de Filas para uma Empresa
Consome os eventos da stream da empresa, dispara alertas e atualiza os placares ao vivo:
```bash
python 02_redis/main.py worker --empresa <UUID_DA_EMPRESA>
```

### 4. Consultar o Leaderboard em Tempo Real
Exibe os Top motoristas por volume e com menor índice de mortalidade:
```bash
python 02_redis/main.py ranking --empresa <UUID_DA_EMPRESA>
```

### 5. Reconciliar Placares a partir do PostgreSQL
Reconstrói o ranking em memória a partir da Materialized View relacional:
```bash
python 02_redis/main.py reconcile --empresa <UUID_DA_EMPRESA>
```

### 6. Consultar Parâmetros da Empresa com Cache-Aside
```bash
python 02_redis/main.py cache-config --empresa <UUID_DA_EMPRESA>
```

---

## 🧪 Executando os Testes Automatizados

Os testes utilizam `fakeredis`, executando em milissegundos sem gastar quota do Upstash e sem necessidade de conexão ativa com a internet:

```bash
# Execução via unittest nativo:
python -m unittest discover -s 02_redis/tests

# Ou via pytest:
pytest 02_redis/tests/
```
