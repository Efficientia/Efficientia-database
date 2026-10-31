# Módulo Relacional e Governança Transacional (PostgreSQL)

O módulo relacional constitui o núcleo transacional de autoridade do ecossistema Efficientia, projetado sob os princípios da modelagem em Terceira Forma Normal (3FN), Forma Normal de Boyce-Codd (FNBC) e arquitetura multimodelo com isolamento estrito de domínios (*multi-tenant*).

Este componente governa o ciclo de vida operacional do transporte pecuário (da fazenda de recria/engorda ao desembarcadouro frigorífico), garantindo auditoria imutável, conformidade com a Lei Geral de Proteção de Dados (LGPD), parametrização operacional customizada por tenant, árvore hierárquica recursiva de anomalias, integração orientada a eventos (*Transactional Outbox Pattern*) e consolidação dimensional de indicadores sanitários em tempo hábil.

---

## 1. Visão Geral da Tecnologia

O PostgreSQL 16 atua como a única fonte da verdade (*Single Source of Truth*) para os dados cadastrais, contratuais, fiscais e operacionais.

### Capacidades Centrais da Modelagem
* **Segregação Física em Esquemas Funcionais**: Particionamento lógico em quatro esquemas dedicados (`sc_corporativo`, `sc_frota`, `sc_operacao` e `sc_auditoria`), delimitando fronteiras de contexto e políticas granulares de acesso (*RBAC*).
* **Herança Objeto-Relacional Nativa (`INHERITS`)**: Modelagem polimórfica para a frota rodoviária, compartilhando atributos estruturais na tabela base e segregando métricas exclusivas (odômetro em cavalos mecânicos versus capacidade volumétrica de cabeças em carretas boiadeiras).
* **Hierarquia Recursiva com Prevenção de Ciclos**: Catálogo de anomalias com autorrelacionamento hierárquico em múltiplos níveis, protegido por gatilhos em tempo de execução (`fn_verificar_ciclo_anomalia`) e explorado via consultas recursivas (`WITH RECURSIVE`).
* **Padrão Transacional de Mensageria (*Transactional Outbox Pattern*)**: Emissão síncrona e atômica de eventos de domínio em formato `JSONB` no momento exato das alterações de estado da viagem, permitindo desacoplamento seguro e transmissão para corretores de mensagens e réplicas em grafo.
* **Auditoria Imutável e Recuperação Cirúrgica**: Rastreamento de modificações `DML` via gatilhos com sanitização automática de dados confidenciais (expurgo de credenciais) e procedimento armazenado para reversão cirúrgica de tuplas a partir do snapshot `JSONB`.
* **Governança Ativa e Métricas de Engajamento**: Dicionário de dados vivo integrado ao catálogo interno do sistema (`pg_catalog`), identificação de dados pessoais para LGPD e consolidação analítica de adoção diária e mensal (*DAU / MAU / Stickiness*).
* **Camada Dimensional Integrada (*Data Mart OLAP*)**: Visões de dimensão, visão fato com cálculo em tempo de execução de quebras de inventário e visão materializada mensal indexada com funções de janela (*Window Functions*) para acompanhamento contínuo de mortalidade.

---

## 2. Modelo Conceitual

O modelo conceitual do módulo relacional compreende três representações fundamentais: o **Diagrama Entidade-Relacionamento Transacional e de Governança**, o **Modelo de Especialização de Frota** e o **Modelo Dimensional (*Star Schema*)**.

### 2.1 Diagrama Entidade-Relacionamento (Transacional e Governança)

```mermaid
erDiagram
    TB_ENDERECO ||--o{ TB_EMPRESA : "localiza (endereco_id)"
    TB_ENDERECO ||--o{ TB_FAZENDA : "localiza (endereco_id)"
    TB_ENDERECO ||--o{ TB_UNIDADE_FRIGORIFICA : "localiza (endereco_id)"

    TB_EMPRESA ||--|| TB_CONFIGURACAO_OPERACAO : "parametriza (empresa_id UK)"
    TB_EMPRESA ||--o{ TB_USUARIO : "vincula (empresa_id)"
    TB_EMPRESA ||--o{ TB_VEICULO_CAVALO : "opera (empresa_id)"
    TB_EMPRESA ||--o{ TB_VEICULO_CARRETA : "opera (empresa_id)"
    TB_EMPRESA ||--o{ TB_RELATORIO_VIAGEM : "isola tenant (empresa_id)"
    TB_EMPRESA ||--o{ TB_OUTBOX_EVENTO : "proprietaria (empresa_id)"

    TB_USUARIO ||--o{ TB_FAZENDA : "responde como pecuarista (pecuarista_id)"
    TB_USUARIO ||--o{ TB_UNIDADE_FRIGORIFICA : "supervisiona como analista (analista_id)"
    TB_USUARIO ||--o{ TB_MONITORAMENTO_DAU : "registra presenca (usuario_id)"
    TB_USUARIO ||--o{ TB_RELATORIO_VIAGEM : "conduz / manobra / maneja"
    TB_USUARIO ||--o{ TB_AUDITORIA_ANALISE : "emite parecer (analista_id)"

    TB_FAZENDA ||--o{ TB_RELATORIO_VIAGEM : "origina lote (fazenda_id)"
    TB_VEICULO_CAVALO ||--o{ TB_RELATORIO_VIAGEM : "traciona (cavalo_id)"
    TB_VEICULO_CARRETA ||--o{ TB_RELATORIO_VIAGEM : "acondiciona carga (carreta_id)"

    TB_RELATORIO_VIAGEM ||--o{ TB_PARADA_IMPREVISTA : "registra pausa (relatorio_id)"
    TB_DOMINIO_MOTIVO_PARADA ||--o{ TB_PARADA_IMPREVISTA : "tipifica (dominio_parada_id)"

    TB_RELATORIO_VIAGEM ||--o{ TB_ANOMALIA_EMBARQUE : "aponta na origem (relatorio_id)"
    TB_RELATORIO_VIAGEM ||--o{ TB_ANOMALIA_DESEMBARQUE : "aponta no destino (relatorio_id)"
    TB_DOMINIO_ANOMALIA ||--o{ TB_ANOMALIA_EMBARQUE : "classifica (dominio_anomalia_id)"
    TB_DOMINIO_ANOMALIA ||--o{ TB_ANOMALIA_DESEMBARQUE : "classifica (dominio_anomalia_id)"
    TB_DOMINIO_ANOMALIA ||--o{ TB_DOMINIO_ANOMALIA : "subordina-se (anomalia_pai_id)"

    TB_RELATORIO_VIAGEM ||--o{ TB_AUDITORIA_ANALISE : "avalia-se em (relatorio_id)"

    TB_ENDERECO {
        uuid id PK
        varchar cep
        varchar logradouro
        varchar numero
        varchar cidade
        char estado
    }

    TB_EMPRESA {
        uuid id PK
        uuid endereco_id FK
        varchar nome
        varchar razao_social
        varchar codigo_interno
        varchar email UK
        varchar cnpj UK
    }

    TB_CONFIGURACAO_OPERACAO {
        uuid id PK
        uuid empresa_id FK "UK (1:1)"
        int tempo_max_viagem_horas
        int mortalidade_bloqueio_cabecas
        int prazo_analise_horas
        numeric meta_mortalidade
        int qtd_assinaturas_obrigatorias
        boolean alerta_sirene_re
        int alerta_inspecao_dias
        boolean alerta_cnh_vencida
        int alerta_tempo_parada_imprevista
        timestamptz atualizado_em
    }

    TB_USUARIO {
        uuid id PK
        uuid empresa_id FK
        ty_tipo_usuario tipo
        varchar cargo
        ty_nivel_acesso nivel_acesso
        varchar cpf UK
        varchar cnh_numero
        ty_categoria_cnh categoria_cnh
        date data_vencimento_cnh
        varchar nome_completo
        date data_nascimento
        varchar email UK
        varchar telefone
        varchar senha_hash
        text url_assinatura_geral
        varchar status_cadastro
    }

    TB_FAZENDA {
        uuid id PK
        uuid empresa_id FK
        uuid pecuarista_id FK
        uuid endereco_id FK
        varchar nome
        varchar razao_social
        varchar cnpj
    }

    TB_UNIDADE_FRIGORIFICA {
        uuid id PK
        uuid empresa_id FK
        uuid analista_id FK
        uuid endereco_id FK
        varchar nome
        varchar cnpj
        int qtd_currais
    }

    TB_RELATORIO_VIAGEM {
        uuid id PK
        uuid empresa_id FK
        ty_status_diario status
        uuid fazenda_id FK
        uuid motorista_id FK
        uuid manobrista_id FK
        uuid curraleiro_id FK
        uuid cavalo_id FK
        uuid carreta_id FK
        varchar numero_gta UK
        varchar numero_nota_fiscal
        int capacidade_carga_utilizada
        date data_embarque
        time horario_embarque
        time horario_saida_propriedade
        int km_saida_embarcadouro
        date data_chegada_unidade
        time horario_chegada_unidade
        time horario_desembarque
        int km_chegada_desembarcadouro
        varchar numero_curral
        boolean sirene_re_funcionou
        int qtd_machos
        int qtd_femeas
        int qtd_marrucos
        int qtd_em_pe
        int qtd_deitado
        int qtd_morto
        int qtd_emergencia
        text url_laudo_mortalidade
        text motivo_emergencia
        text comentarios
        text url_assinatura_pecuarista
        text url_assinatura_motorista
        text url_assinatura_manobrista
        text url_assinatura_curraleiro
        timestamptz criado_em
        timestamptz enviado_em
    }

    TB_PARADA_IMPREVISTA {
        uuid id PK
        uuid relatorio_id FK
        uuid dominio_parada_id FK
        timestamptz data_hora_inicio
        timestamptz data_hora_fim
    }

    TB_DOMINIO_MOTIVO_PARADA {
        uuid id PK
        varchar codigo UK
        varchar descricao
        boolean ativo
    }

    TB_DOMINIO_ANOMALIA {
        uuid id PK
        uuid anomalia_pai_id FK
        varchar tipo_etapa
        varchar codigo
        varchar descricao
        boolean ativo
    }

    TB_ANOMALIA_EMBARQUE {
        uuid id PK
        uuid relatorio_id FK
        uuid dominio_anomalia_id FK
        varchar descricao_outros
    }

    TB_ANOMALIA_DESEMBARQUE {
        uuid id PK
        uuid relatorio_id FK
        uuid dominio_anomalia_id FK
        varchar descricao_outros
    }

    TB_AUDITORIA_ANALISE {
        uuid id PK
        uuid relatorio_id FK
        uuid analista_id FK
        timestamptz data_hora_analise
        boolean aprovado
        varchar motivo_rejeicao
        text parecer_tecnico
    }

    TB_OUTBOX_EVENTO {
        uuid id PK
        uuid empresa_id FK
        varchar tipo_evento
        varchar agregado_tipo
        uuid agregado_id
        jsonb payload
        timestamptz criado_em
        timestamptz processado_em
        int erro_tentativas
        text ultimo_erro
    }

    TB_CATALOGO_DADOS {
        uuid id PK
        varchar esquema_nome
        varchar tabela_nome
        varchar coluna_nome
        text descricao
        text regra_negocio_critica
        varchar nivel_acesso_leitura
        varchar nivel_acesso_escrita
        boolean dado_pessoal_lgpd
        timestamptz atualizado_em
    }

    TB_AUDITORIA_LOG {
        uuid id PK
        uuid empresa_id
        varchar tabela_afetada
        varchar operacao
        varchar usuario_db
        jsonb dados_antigos
        jsonb dados_novos
        timestamptz data_hora
    }

    TB_MONITORAMENTO_DAU {
        uuid id PK
        uuid usuario_id FK "UK (usuario_id, data_acesso)"
        date data_acesso
    }

    TB_HISTORICO_BACKUP {
        uuid id PK
        varchar operacao
        varchar status
        varchar nome_banco
        varchar arquivo_dump
        bigint tamanho_bytes
        char checksum_sha256
        timestamptz iniciado_em
        timestamptz finalizado_em
        varchar executado_por
        text mensagem_erro
    }
```

### 2.2 Modelo de Generalização e Especialização da Frota (`INHERITS`)

A herança relacional compartilha dados cadastrais de identificação e emplacamento, segregando atributos funcionais:

```mermaid
classDiagram
    class tb_veiculo_base {
        <<Superclasse sc_frota>>
        +UUID id
        +UUID empresa_id
        +VARCHAR placa
        +BOOLEAN ativo
        +DATE data_vencimento_inspecao
    }

    class tb_veiculo_cavalo {
        <<Subclasse INHERITS sc_frota>>
        +INTEGER km_acumulado
    }

    class tb_veiculo_carreta {
        <<Subclasse INHERITS sc_frota>>
        +INTEGER capacidade_cabecas
    }

    class vw_dim_frota {
        <<Visao Polimorfica Analitica>>
        +UUID sk_veiculo
        +UUID fk_empresa
        +VARCHAR placa
        +BOOLEAN status_ativo
        +TEXT tipo_veiculo
    }

    tb_veiculo_base <|-- tb_veiculo_cavalo : INHERITS
    tb_veiculo_base <|-- tb_veiculo_carreta : INHERITS
    tb_veiculo_base ..> vw_dim_frota : projeta
```

### 2.3 Modelo Conceitual Dimensional (*Star Schema*)

Para relatórios gerenciais e análises sanitárias, a camada dimensional desacopla o tráfego analítico:

```mermaid
flowchart TB
    DIM_EMP["vw_dim_empresa<br/>(sk_empresa)"]
    DIM_COL["vw_dim_colaborador<br/>(sk_colaborador)"]
    DIM_FRO["vw_dim_frota<br/>(sk_veiculo)"]
    DIM_LOC["vw_dim_localidade<br/>(sk_localidade)"]

    FATO["vw_fato_transporte_animal<br/>(sk_fato_viagem, quebra_inventario_cabecas, km_rodados)"]

    MV["mv_analise_mortalidade_mensal<br/>(taxa_mortalidade_percentual, acumulado_mortes_ano, rank_mortalidade_motorista)"]

    DIM_EMP -->|"1:N"| FATO
    DIM_COL -->|"1:N"| FATO
    DIM_FRO -->|"1:N"| FATO
    DIM_LOC -->|"1:N"| FATO
    FATO ==>|"Agregacao Mensal"| MV
```

---

## 3. Estrutura Estratégica do Diretório

```text
01_postgresql/
├── README.md                                     # Documentacao tecnica e modelo conceitual
├── modelo_logico.pdf                             # Diagrama visual relacional exportado
├── modelo_logico_dbdiagram.dbml                  # Especificacao DBML formal sincronizada
│
├── 01_ddl/                                       # Estruturas fisicas, esquemas e tabelas
│   ├── 01_schemas_e_tipos.sql                    # Extensao pgcrypto, 4 esquemas e 4 tipos ENUM
│   ├── 02_catalogo_e_auditoria.sql               # Metadados, log transacional e presenca DAU
│   ├── 03_corporativo_e_frota.sql                # Cadastros mestres e heranca de frota
│   ├── 04_tabelas_transacionais.sql              # Relatorio de viagem, paradas, anomalias e outbox
│   └── 05_governanca_backup_e_hierarquia.sql     # Atributo LGPD, historico de backup e hierarquia de anomalias
│
├── 02_constraints_and_indexes/                   # Indices e otimizacao fisica
│   └── 01_keys_e_indexes.sql                     # Indices B-Tree multi-tenant, FKs e indices parciais
│
├── 03_views/                                     # Camada analitica e governanca
│   ├── 01_datamart_bi.sql                        # Dimensoes, fato de transporte e visao materializada
│   └── 02_views_governanca_dau_e_hierarquia.sql  # Arvore recursiva, rollup de ocorrencias, catalogo e DAU/MAU
│
├── 04_functions/                                 # Funcoes procedurais em PL/pgSQL
│   ├── 01_fn_registrar_auditoria.sql             # Trilha JSONB com exclusao de credenciais
│   ├── 02_fn_registrar_dau.sql                   # Gravacao idempotente de presenca diaria
│   ├── 03_fn_validar_alocacao_viagem.sql         # Validador de vigencia de CNH e inspecao veicular
│   ├── 04_fn_gerar_outbox_relatorio.sql          # Produtor transacional de eventos Outbox
│   └── 05_fn_hierarquia_e_recuperacao.sql        # Funcao anti-ciclo, extrator de subarvore e volumetria
│
├── 05_triggers/                                  # Gatilhos sincronos
│   ├── 01_tg_auditoria.sql                       # Triggers AFTER de log em tabelas de negocio
│   ├── 02_tg_validacoes_operacionais.sql         # Triggers BEFORE de validacao e AFTER de Outbox
│   └── 03_tg_hierarquia_anomalia.sql             # Trigger BEFORE para prevencao de ciclos hierarquicos
│
├── 06_procedures/                                # Procedimentos transacionais
│   ├── 01_sp_aprovar_relatorio.sql               # Aprovacao veterinaria com trava pessimista
│   ├── 02_sp_registrar_anomalia.sql              # Roteamento seguro de anomalias por etapa
│   └── 03_sp_governanca_e_recuperacao.sql        # Sincronizacao de catalogo, registro de backup e restore cirurgico
│
├── 07_dataload/                                  # Cargas de dados modulares
│   ├── 01_carga_catalogo_dados.sql               # Dicionario inicial de governanca de dados
│   ├── 02_carga_corporativo.sql                  # Enderecos, empresas, configuracoes e usuarios
│   ├── 03_carga_frota_e_dominios.sql             # Frotas, parceiros, motivos de parada e anomalias
│   ├── 04_carga_relatorios_viagem.sql            # Diarios de rota transacionais
│   ├── 05_carga_paradas_e_anomalias.sql          # Paradas imprevistas e ocorrencias na rota
│   ├── 06_carga_auditoria_analise.sql            # Pareceres tecnicos de analise veterinaria
│   ├── 07_carga_outbox_eventos.sql               # Eventos persistidos para mensageria assincrona
│   ├── 08_carga_monitoramento_dau.sql            # Historico de acesso diario para metricas DAU/MAU
│   └── 09_carga_complementar_governanca.sql      # Marcacao LGPD, arvore hierarquica e historico de backup
│
├── 08_backup/                                    # Procedimentos operacionais de recuperacao
│   ├── backup.sh                                 # Rotina automatizada de dump compactado com SHA-256
│   └── restore.sh                                # Rotina de restauracao limpa com conferencia de integridade
│
├── 09_rollback/                                  # Scripts para desfazimento controlado
│   ├── 01_drop_views_e_rotinas.sql               # Remocao de visoes, procedimentos e triggers
│   └── 02_drop_tudo.sql                          # Teardown completo de tabelas, tipos e esquemas
│
├── 10_tests/                                     # Baterias de testes automatizados
│   ├── 01_test_regras_negocio_e_validacoes.sql   # Testes de bloqueio de CNH, categorias e aprovacao
│   ├── 02_test_hierarquia_recursiva.sql          # Testes anti-ciclo, validacao de etapas e subarvore
│   ├── 03_test_auditoria_dau_e_recuperacao.sql   # Testes de auditoria, registro DAU e restore cirurgico
│   └── check_postgresql.sh                       # Executor bash automatizado das baterias
│
└── docs/                                         # Documentacao tecnica complementar
    ├── NORMALIZACAO.md                           # Prova formal de 1FN a 5FN por entidade
    ├── verificacao_normalizacao.sql              # Script SQL de validacao de integridade relacional
    ├── OTIMIZACAO_EXPLAIN_ANALYZE.md             # Evidencias de planos de execucao antes/depois de indices
    ├── explain_analyze.sql                       # Consultas reproduziveis de analise de custo e buffers
    └── BACKUP_E_RECUPERACAO.md                   # Politica operacional de RPO/RTO e runbook de contingencia
```

---

## 4. Convenções e Tipagem

### 4.1 Tipos Enumerados (`ENUM`)

| Esquema | Tipo | Valores Válidos | Propósito de Negócio |
| :--- | :--- | :--- | :--- |
| `sc_corporativo` | `ty_tipo_usuario` | `'administrador'`, `'motorista'`, `'manobrista'`, `'analista'`, `'pecuarista'`, `'curraleiro'` | Perfis de acesso e atribuições funcionais |
| `sc_corporativo` | `ty_nivel_acesso` | `'administrativo'`, `'auditoria'`, `'conducao'` | Políticas de controle de acesso aos recursos |
| `sc_corporativo` | `ty_categoria_cnh` | `'a'`, `'b'`, `'c'`, `'d'`, `'e'` | Classificação da habilitação para validação de trânsito |
| `sc_operacao` | `ty_status_diario` | `'rascunho'`, `'pendente'`, `'aprovado'`, `'reprovado'` | Ciclo transacional do relatório de viagem |

### 4.2 Códigos Semânticos de Exceção (`SQLSTATE`)

| Código | Descrição Semântica | Disparador |
| :--- | :--- | :--- |
| `P0001` | Tentativa de alocação de motorista sem CNH cadastrada | `fn_validar_alocacao_viagem()` |
| `P0002` | Tentativa de alocação de condutor com CNH vencida | `fn_validar_alocacao_viagem()` |
| `P0003` | Tentativa de alocação de veículo com vistoria/inspeção vencida | `fn_validar_alocacao_viagem()` |
| `P0004` | Condutor sem habilitação categoria 'E' para carreta boiadeira | `fn_validar_alocacao_viagem()` |
| `P0005` | Tentativa de aprovação de diário que não está pendente | `sp_aprovar_relatorio()` |
| `P0006` | Etapa operacional informada inválida (deve ser EMBARQUE ou DESEMBARQUE) | `sp_registrar_anomalia()` |
| `P0007` | Código de anomalia inexistente ou inativo no catálogo | `sp_registrar_anomalia()` |
| `P0008` | Detecção de ciclo hierárquico ou autorreferência no catálogo de anomalias | `fn_verificar_ciclo_anomalia()` |
| `P0009` | Incompatibilidade de etapa operacional entre nó pai e nó filho na árvore | `fn_verificar_ciclo_anomalia()` |
| `P0010` | Registro de log não encontrado para restauração cirúrgica | `sp_restaurar_registro_auditoria()` |
| `P0011` | Tabela não habilitada para restauração cirúrgica automatizada | `sp_restaurar_registro_auditoria()` |
| `P0012` | Ausência de snapshot anterior (`dados_antigos`) no registro de log | `sp_restaurar_registro_auditoria()` |

---

## 5. Scripts de Carga e Automação

Os scripts da pasta `07_dataload/` executam com garantia de idempotência (`ON CONFLICT DO UPDATE` ou `DO NOTHING`):

1. **`01_carga_catalogo_dados.sql`**: Mapeia todas as colunas físicas dos esquemas, regras de negócio e limites de permissão RBAC.
2. **`02_carga_corporativo.sql`**: Popula sedes, empresas clientes, parâmetros de SLA e colaboradores.
3. **`03_carga_frota_e_dominios.sql`**: Insere unidades tratoras, reboques boiadeiros, fazendas, frigoríficos e itens de domínio.
4. **`04_carga_relatorios_viagem.sql`**: Insere viagens transacionais completas contendo GTAs, notas fiscais, odômetros e animais.
5. **`05_carga_paradas_e_anomalias.sql`**: Insere ocorrências de paradas imprevistas e apontamentos de desvios operacionais.
6. **`06_carga_auditoria_analise.sql`**: Registra as deliberações técnicas emitidas pela equipe veterinária.
7. **`07_carga_outbox_eventos.sql`**: Insere mensagens operacionais para simulação de relay assíncrono.
8. **`08_carga_monitoramento_dau.sql`**: Constrói o histórico de presença diária de usuários para métricas analíticas.
9. **`09_carga_complementar_governanca.sql`**: Classifica os atributos pessoais sob escopo da LGPD, estrutura a árvore de anomalias em três níveis (raízes operacionais, categorias temáticas e anomalias folhas) e registra histórico inicial de backups.

---

## 6. Validação e Casos de Uso

### 6.1 Execução de Consultas Analíticas e Hierárquicas

```sql
-- 1. Consultar arvore hierarquica de anomalias com nivel e caminho
SELECT id, tipo_etapa, codigo, nivel_hierarquia, caminho_codigos, eh_folha
FROM sc_operacao.vw_arvore_dominio_anomalia
ORDER BY tipo_etapa, nivel_hierarquia, codigo;

-- 2. Consultar consolidacao de ocorrencias acumuladas por subarvore
SELECT anomalia_id, tipo_etapa, nivel_hierarquia, codigo,
       ocorrencias_diretas, ocorrencias_subarvore, ranking_no_nivel, participacao_etapa_perc
FROM sc_operacao.vw_ocorrencias_por_arvore_anomalia
WHERE nivel_hierarquia <= 2
ORDER BY tipo_etapa, ocorrencias_subarvore DESC;

-- 3. Acompanhar adocao diaria, media movel e stickiness (DAU / MAU)
SELECT data_referencia, dau, dau_dia_anterior, media_movel_7d, mau_30d, stickiness_perc
FROM sc_auditoria.vw_metricas_dau_mau
ORDER BY data_referencia DESC
LIMIT 14;

-- 4. Inspecionar conformidade de documentacao ativa e campos LGPD
SELECT esquema_nome, tabela_nome, total_colunas, colunas_documentadas,
       cobertura_documentacao_perc, qtd_colunas_lgpd, contem_dados_pessoais
FROM sc_auditoria.vw_resumo_catalogo_tabelas
ORDER BY cobertura_documentacao_perc ASC;

-- 5. Monitorar status dos backups fisicos e conformidade com RPO de 24h
SELECT nome_banco, arquivo_dump, tamanho_mb, duracao_segundos,
       horas_desde_execucao, dentro_janela_rpo_24h, status
FROM sc_auditoria.vw_status_backups
ORDER BY iniciado_em DESC
LIMIT 5;
```

### 6.2 Recuperação Cirúrgica em Nível de Linha

Para restaurar um registro modificado acidentalmente sem recorrer à restauração total da base:
```sql
-- Localiza o log da operacao indesejada
SELECT id, tabela_afetada, operacao, usuario_db, data_hora
FROM sc_auditoria.tb_auditoria_log
WHERE tabela_afetada = 'sc_operacao.tb_relatorio_viagem'
ORDER BY data_hora DESC
LIMIT 1;

-- Executa a reversao cirurgica com snapshot historico imutavel
CALL sc_auditoria.sp_restaurar_registro_auditoria('c9aa0000-0000-4000-8000-000000000001');
```

---

## 7. Instruções de Execução Local

### 7.1 Pré-Requisitos
* PostgreSQL 16 instalado e ativo.
* Cliente de terminal `psql` disponível no `PATH`.

### 7.2 Implantação Completa Passo a Passo

```bash
# 1. Configuracao da conexao
export DATABASE_URL="postgresql://postgres:postgrespassword@localhost:5432/efficientia"

# 2. Execucao de DDLs
psql "$DATABASE_URL" -f 01_postgresql/01_ddl/01_schemas_e_tipos.sql
psql "$DATABASE_URL" -f 01_postgresql/01_ddl/02_catalogo_e_auditoria.sql
psql "$DATABASE_URL" -f 01_postgresql/01_ddl/03_corporativo_e_frota.sql
psql "$DATABASE_URL" -f 01_postgresql/01_ddl/04_tabelas_transacionais.sql
psql "$DATABASE_URL" -f 01_postgresql/01_ddl/05_governanca_backup_e_hierarquia.sql

# 3. Indices e Chaves
psql "$DATABASE_URL" -f 01_postgresql/02_constraints_and_indexes/01_keys_e_indexes.sql

# 4. Funcoes e Triggers
psql "$DATABASE_URL" -f 01_postgresql/04_functions/01_fn_registrar_auditoria.sql
psql "$DATABASE_URL" -f 01_postgresql/04_functions/02_fn_registrar_dau.sql
psql "$DATABASE_URL" -f 01_postgresql/04_functions/03_fn_validar_alocacao_viagem.sql
psql "$DATABASE_URL" -f 01_postgresql/04_functions/04_fn_gerar_outbox_relatorio.sql
psql "$DATABASE_URL" -f 01_postgresql/04_functions/05_fn_hierarquia_e_recuperacao.sql

psql "$DATABASE_URL" -f 01_postgresql/05_triggers/01_tg_auditoria.sql
psql "$DATABASE_URL" -f 01_postgresql/05_triggers/02_tg_validacoes_operacionais.sql
psql "$DATABASE_URL" -f 01_postgresql/05_triggers/03_tg_hierarquia_anomalia.sql

# 5. Procedures e Visoes
psql "$DATABASE_URL" -f 01_postgresql/06_procedures/01_sp_aprovar_relatorio.sql
psql "$DATABASE_URL" -f 01_postgresql/06_procedures/02_sp_registrar_anomalia.sql
psql "$DATABASE_URL" -f 01_postgresql/06_procedures/03_sp_governanca_e_recuperacao.sql

psql "$DATABASE_URL" -f 01_postgresql/03_views/01_datamart_bi.sql
psql "$DATABASE_URL" -f 01_postgresql/03_views/02_views_governanca_dau_e_hierarquia.sql

# 6. Carga de Dados Inicial
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/01_carga_catalogo_dados.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/02_carga_corporativo.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/03_carga_frota_e_dominios.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/04_carga_relatorios_viagem.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/05_carga_paradas_e_anomalias.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/06_carga_auditoria_analise.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/07_carga_outbox_eventos.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/08_carga_monitoramento_dau.sql
psql "$DATABASE_URL" -f 01_postgresql/07_dataload/09_carga_complementar_governanca.sql

# 7. Execucao de Testes Automatizados
chmod +x 01_postgresql/10_tests/check_postgresql.sh
./01_postgresql/10_tests/check_postgresql.sh
```

---

## 8. Manutenção e Boas Práticas

### Rotina de Atualização de Visão Materializada
A consolidação de indicadores na visão materializada deve ser agendada via rotina operacional:
```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY sc_operacao.mv_analise_mortalidade_mensal;
```
Graças ao índice único `uidx_mv_analise_mortalidade`, o comando executa sem bloqueio de leitura.

### Rotinas de Backup e Auditoria
* O script `01_postgresql/08_backup/backup.sh` deve ser configurado em agendador diário para garantir conformidade com o RPO estabelecido de 24 horas.
* O catálogo de dados deve ser mantido sincronizado executando `CALL sc_auditoria.sp_sincronizar_catalogo_dados(FALSE)` após qualquer alteração estrutural no banco.
* As evidências de otimização detalhadas e a prova matemática de normalização encontram-se documentadas em [NORMALIZACAO.md](file:///c:/Users/noecusiquispe-ieg/OneDrive%20-%20Instituto%20J&F/%C3%81rea%20de%20Trabalho/Modelagem%20de%20Dados/Efficientia-database/01_postgresql/docs/NORMALIZACAO.md), [OTIMIZACAO_EXPLAIN_ANALYZE.md](file:///c:/Users/noecusiquispe-ieg/OneDrive%20-%20Instituto%20J&F/%C3%81rea%20de%20Trabalho/Modelagem de Dados/Efficientia-database/01_postgresql/docs/OTIMIZACAO_EXPLAIN_ANALYZE.md) e [BACKUP_E_RECUPERACAO.md](file:///c:/Users/noecusiquispe-ieg/OneDrive%20-%20Instituto%20J&F/%C3%81rea%20de%20Trabalho/Modelagem%20de%20Dados/Efficientia-database/01_postgresql/docs/BACKUP_E_RECUPERACAO.md).
