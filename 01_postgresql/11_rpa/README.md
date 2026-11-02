# Efficientia RPA - Sincronização Bidirecional de Bancos de Dados

Mecanismo de automação de processos (RPA) desenvolvido em Python para execução de sincronização bidirecional e reconciliação contínua de dados entre duas arquiteturas de banco de dados do ecossistema Efficientia:

- **Banco 1 (Logística Operacional / Instância Operacional (DB1)):** Baseado na estrutura `Efficientia.sql`, contendo as tabelas operacionais `empresa` e `motorista`.
- **Banco 2 (Corporativo e Aplicações / Instância Corporativa (DB2)):** Baseado na estrutura canônica do repositório `Efficientia-database`, contendo as tabelas `sc_corporativo.tb_empresa` e `sc_corporativo.tb_usuario` (na qual os registros de motoristas são identificados pelo atributo `tipo = 'motorista'`).

O sistema assegura integridade referencial por meio de resolução dinâmica de chaves estrangeiras, garantia de idempotência via hashes canônicos SHA-256 e rastreabilidade contínua em trilha de auditoria (`rpa_sync_log`).

---

## Interface de Linha de Comando (CLI)

O ponto de entrada operacional do RPA é gerenciado pelo script `main.py`. A CLI disponibiliza subcomandos para execução pontual, operação contínua como serviço, inicialização de schemas, diagnóstico de dados e auditoria.

### Sintaxe Geral

```bash
python main.py <comando> [opções]
```

### Comandos Disponíveis

| Comando | Descrição | Opções |
| :--- | :--- | :--- |
| `run` | Executa um ciclo único de sincronização bidirecional. | `--dry-run` |
| `daemon` | Executa o processo de sincronização em loop contínuo com intervalo programado. | `--interval <segundos>`, `--dry-run` |
| `init-db` | Cria as tabelas necessárias em ambos os bancos e opcionalmente insere dados de teste. | `--seed` |
| `stats` | Exibe a volumetria atual das tabelas e o status de conexão dos bancos. | Nenhuma |
| `audit` | Exibe os registros mais recentes da tabela de auditoria (`rpa_sync_log`). | `--limit <número>` |

---

### Detalhamento dos Comandos e Exemplos de Uso

#### 1. Ciclo Único de Sincronização (`run`)

Executa uma rodada completa de sincronização (Banco 1 para Banco 2 e Banco 2 para Banco 1) e encerra o processo:

```bash
python main.py run
```

Para validar o fluxo e identificar alterações pendentes sem persistir nenhuma modificação nos bancos de dados, utilize o modo de simulação (*dry-run*):

```bash
python main.py run --dry-run
```

#### 2. Execução Contínua em Segundo Plano (`daemon`)

Executa o serviço em execução contínua, realizando ciclos periódicos de sincronização:

```bash
# Execução utilizando o intervalo configurado no ambiente (padrão: 30 segundos)
python main.py daemon

# Execução definindo intervalo customizado de 60 segundos
python main.py daemon --interval 60

# Execução contínua em modo de simulação (sem persistência)
python main.py daemon --interval 30 --dry-run
```

Para interromper o serviço, envie um sinal de encerramento (`SIGINT` ou `Ctrl + C`). O encerramento seguro (*graceful shutdown*) aguarda a conclusão do ciclo corrente antes de finalizar.

#### 3. Inicialização e Provisionamento de Tabelas (`init-db`)

Cria as estruturas de tabelas em ambos os bancos de dados configurados (incluindo a tabela de auditoria `rpa_sync_log`) e popula dados iniciais para homologação:

```bash
# Cria tabelas e insere registros de teste (empresas e motoristas)
python main.py init-db --seed

# Cria apenas as estruturas de tabelas, sem popular dados
python main.py init-db
```

#### 4. Diagnóstico e Estatísticas dos Bancos (`stats`)

Exibe a contagem atual de registros nas tabelas gerenciadas em ambas as pontas e lista os primeiros registros identificados:

```bash
python main.py stats
```

#### 5. Consulta da Trilha de Auditoria (`audit`)

Lista os registros persistidos na tabela `rpa_sync_log`, exibindo tipo de entidade, direção do fluxo, identificadores de origem e destino, ação realizada (`INSERT`, `UPDATE`, `SKIPPED`) e hash de dados:

```bash
# Exibe os últimos 20 registros de auditoria (padrão)
python main.py audit

# Exibe quantidade personalizada de registros
python main.py audit --limit 50
```

---

## Arquitetura de Sincronização

### 1. Resolução e Mapeamento de Chaves Estrangeiras (FK Mapping)
O vínculo entre as tabelas `empresa` e `motorista`/`usuario` é baseado no identificador numérico interno (`id`) de cada banco. Como esses identificadores são gerados independentemente por sequências distintas em cada provedor, o RPA utiliza a chave natural da empresa (**CNPJ**, normalizado em 14 dígitos numéricos) como elo de correlação. Durante o trânsito do registro de motorista, o sistema resolve a chave estrangeira local consultando a empresa correspondente pelo CNPJ.

### 2. Idempotência e Detecção de Ciclos de Atualização
Para evitar atualizações infinitas entre as duas bases e assegurar que execuções sucessivas não gerem duplicidade, o sistema:
- Normaliza os campos das entidades (CNPJ, CPF, telefone, e-mail, datas).
- Computa um hash **SHA-256** canônico a partir dos dados normalizados.
- Consulta o histórico de sincronização na tabela `rpa_sync_log`. Caso o hash calculado seja idêntico ao último hash registrado para aquela chave natural, a sincronização é ignorada (`SKIPPED`).
- Caso haja divergência no hash, o sistema propaga a alteração como atualização (`UPDATE`).

### 3. Registro de Auditoria (`rpa_sync_log`)
Todas as operações de integração são registradas em uma tabela de auditoria dedicada, com os seguintes atributos:
- `entity_type`: Tipo da entidade sincronizada (`empresa` ou `motorista`).
- `source_db` e `target_db`: Origem e destino da operação (`db1` ou `db2`).
- `source_id` e `target_id`: Identificadores de registro nas bases correspondentes.
- `natural_key`: Identificador de negócio (CNPJ para empresas; CPF ou e-mail para motoristas).
- `action`: Tipo de ação executada (`INSERT`, `UPDATE`, `SKIPPED`).
- `data_hash`: Hash SHA-256 dos dados no momento da sincronização.
- `synced_at`: Timestamp UTC da operação.
- `error_message`: Detalhes de exceção caso ocorra falha.

---

## Requisitos de Sistema

- Python 3.10 ou superior
- Acesso de rede aos bancos de dados relacionais (PostgreSQL, MySQL ou SQLite)
- Docker e Docker Compose (opcional, para execução conteinerizada)

---

## Instalação e Configuração

### 1. Instalação do Ambiente e Dependências

Crie um ambiente virtual e instale os pacotes requeridos:

```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows
.\venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configuração de Variáveis de Ambiente

Crie o arquivo de configuração local a partir do modelo fornecido:

```bash
cp .env.example .env
```

Edite o arquivo `.env` com as strings de conexão e parâmetros operacionais:

```ini
# Banco 1: Logística Operacional (Instância Operacional (DB1) PostgreSQL / MySQL)
DB1_URL=postgresql+psycopg2://usuario:senha@host-banco-1.efficientia.internal:17645/dbEfficientia?sslmode=require
DB1_EMPRESA_TABLE=empresa
DB1_MOTORISTA_TABLE=motorista

# Banco 2: Corporativo / Aplicações (Instância Corporativa (DB2) PostgreSQL)
DB2_URL=postgresql+psycopg2://postgres.projeto:senha@host-banco-2.efficientia.internal:5432/postgres?sslmode=require
DB2_EMPRESA_TABLE=tb_empresa
DB2_MOTORISTA_TABLE=tb_usuario

# Parâmetros de Execução do RPA
SYNC_INTERVAL_SECONDS=30
LOG_LEVEL=INFO
DEFAULT_SYNC_PASSWORD_HASH=$2a$10$abcdefghijklmnopqrstuvwxyz1234567890
```

#### Parâmetros de Configuração

| Variável | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `DB1_URL` | String | `sqlite:///db1_operacional.db` | URI de conexão SQLAlchemy com o Banco 1 (Operacional). |
| `DB1_EMPRESA_TABLE` | String | `empresa` | Nome da tabela de empresas no Banco 1. |
| `DB1_MOTORISTA_TABLE` | String | `motorista` | Nome da tabela de motoristas no Banco 1. |
| `DB2_URL` | String | `sqlite:///db2_corporativo.db` | URI de conexão SQLAlchemy com o Banco 2 (Corporativo). |
| `DB2_EMPRESA_TABLE` | String | `tb_empresa` | Nome da tabela de empresas no Banco 2 (schema `sc_corporativo`). |
| `DB2_MOTORISTA_TABLE` | String | `tb_usuario` | Nome da tabela de usuários/motoristas no Banco 2 (schema `sc_corporativo`). |
| `SYNC_INTERVAL_SECONDS` | Inteiro | `30` | Intervalo em segundos entre ciclos em modo daemon. |
| `LOG_LEVEL` | String | `INFO` | Nível de detalhamento de log (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `DEFAULT_SYNC_PASSWORD_HASH` | String | Hash predefinido | Hash temporário utilizado para criação de novos registros no destino. |

---

## Execução com Docker

O projeto inclui manifestos para execução conteinerizada em ambientes de produção ou homologação.

### Construção e Execução via Docker Compose

```bash
# Iniciar o serviço em segundo plano
docker compose up -d --build

# Acompanhar os logs do serviço
docker compose logs -f rpa-syncer

# Parar o serviço
docker compose down
```

### Execução via Dockerfile Diretamente

```bash
# Construção da imagem
docker build -t efficientia-rpa:latest .

# Execução em modo daemon com arquivo .env
docker run -d --name efficientia-rpa --env-file .env efficientia-rpa:latest

# Execução de comando pontual (ex.: stats)
docker run --rm --env-file .env efficientia-rpa:latest stats
```

---

## Estrutura do Repositório

```text
efficientia-rpa/
├── config.py                 # Gerenciamento de configurações e variáveis de ambiente
├── database.py               # Configuração de engines SQLAlchemy e gerenciamento de sessões
├── models.py                 # Declaração dos modelos ORM (Banco 1, Banco 2 e Auditoria)
├── mapper.py                 # Funções de normalização, cálculo de hash e mapeamento de campos
├── syncer.py                 # Mecanismo central de sincronização e regras de reconciliação
├── init_schemas.py           # Provisionamento de schemas e carga de dados de homologação
├── main.py                   # Interface de linha de comando (CLI)
├── requirements.txt          # Especificação de dependências do projeto
├── Dockerfile                # Configuração de build da imagem de contêiner
├── docker-compose.yml        # Orquestração do serviço de sincronização
├── .env.example              # Modelo de configuração de variáveis de ambiente
└── tests/                    # Suíte de testes automatizados
    ├── test_bidirectional_sync.py  # Testes de integração, idempotência e dry-run
    └── test_mapper.py              # Testes unitários de mapeamento e normalização
```

---

## Testes Automatizados

A validação da aplicação é realizada por meio do framework `pytest`. Os testes utilizam instâncias SQLite em memória para garantir isolamento e velocidade de execução.

```bash
# Execução da suíte completa de testes
python -m pytest

# Execução detalhada (modo verboso)
python -m pytest -v

# Execução de arquivo de teste específico
python -m pytest tests/test_bidirectional_sync.py -v
```
