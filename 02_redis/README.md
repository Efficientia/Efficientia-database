# Sistema de Filas e Mensageria Assíncrona com Redis (Upstash)

Este diretório contém a implementação da camada de mensageria assíncrona, filas e processamento de eventos do ecossistema **Efficientia**, utilizando **Redis Streams** com **Consumer Groups** e integração ao PostgreSQL via **Transactional Outbox**.

---

## 🏗️ Arquitetura do Fluxo de Eventos

```text
[ Supabase / PostgreSQL ]
   │
   ├─► tb_relatorio_viagem (INSERT / UPDATE status)
   │      │
   │      ▼ (Trigger síncrono ACID)
   └─► tb_outbox_evento
          │
          ▼ (Polling assíncrono via FOR UPDATE SKIP LOCKED)
   [ Outbox Relay Python ]
          │
          ▼ (XADD com suporte a TLS rediss://)
   [ Upstash / Redis Streams ] (efficientia:env:empresa_id:stream:eventos)
          │
          ▼ (XREADGROUP com BLOCK para economia de quota)
   [ Stream Consumer Workers ]
          │
          ├─► Job: AlertaMortalidadeJob (Detecção de óbitos / Laudo SIF)
          ├─► Job: AlertaEmergenciaJob (Animais fadigados / Curral prioritário)
          │
          ├─► Sucesso: XACK
          └─► Falha: Encaminhamento para Dead Letter Queue (stream:dlq)
```

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

## 🚀 Como Executar

A CLI centralizada está disponível em `02_redis/main.py`:

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
Consome os eventos da stream da empresa com confirmação (XACK):
```bash
python 02_redis/main.py worker --empresa <UUID_DA_EMPRESA>
```

### 4. Simular disparo de evento de teste na fila
Publica um evento com óbito simulado para testar os alertas dos workers:
```bash
python 02_redis/main.py test-event --empresa <UUID_DA_EMPRESA> --morto 2 --emergencia 1
```

---

## 🧪 Executando os Testes Automatizados

Os testes utilizam `fakeredis`, o que significa que rodam sem consumir quota do Upstash e sem necessidade de conexão ativa com a internet:

```bash
pytest 02_redis/tests/
```
