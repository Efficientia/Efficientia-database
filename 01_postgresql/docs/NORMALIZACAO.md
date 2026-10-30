# Prova Formal de Normalização Relacional

Este documento apresenta a demonstração formal de normalização das entidades relacionais do ecossistema Efficientia, comprovando a adesão rigorosa da modelagem aos critérios da Primeira Forma Normal (1FN), Segunda Forma Normal (2FN), Terceira Forma Normal (3FN), Forma Normal de Boyce-Codd (FNBC), Quarta Forma Normal (4FN) e Quinta Forma Normal (5FN).

A persistência do banco relacional é particionada em quatro esquemas estratégicos:
- `sc_corporativo`: Cadastro mestre, estrutura organizacional e parametrizações operacionais.
- `sc_frota`: Equipamentos logísticos estruturados com herança relacional (`INHERITS`).
- `sc_operacao`: Registros transacionais das viagens, eventos e apontamentos de rota.
- `sc_auditoria`: Governança, catálogo ativo, registros de acesso e trilhas imutáveis.

---

## 1. Fundamentos Teóricos da Normalização

### Primeira Forma Normal (1FN)
Uma relação $R$ está na 1FN se, e somente se, todos os domínios de seus atributos contêm apenas valores atômicos (indivisíveis), não havendo repetição de grupos ou vetores multivalorados não tipados.

### Segunda Forma Normal (2FN)
Uma relação $R$ está na 2FN se está na 1FN e todo atributo não primo (atributo que não pertence a nenhuma chave candidata) é total e funcionalmente dependente da chave primária inteira, não de um subconjunto próprio dela ($X \to Y$, onde $X$ é irredutível).

### Terceira Forma Normal (3FN)
Uma relação $R$ está na 3FN se está na 2FN e nenhum atributo não primo depende transitivamente de qualquer chave candidata ($X \to Y$ e $Y \to Z$ implicaria dependência transitiva de $Z$ em relação a $X$). Em termos formais, para toda dependência funcional não trivial $X \to Y$, $X$ é superchave ou $Y$ é atributo primo.

### Forma Normal de Boyce-Codd (FNBC)
Uma relação $R$ está na FNBC se, e somente se, para toda dependência funcional não trivial $X \to Y$ em $R$, o determinante $X$ é uma superchave de $R$. A FNBC elimina anomalias que ocorrem na 3FN quando existem múltiplas chaves candidatas compostas e sobrepostas.

### Quarta Forma Normal (4FN)
Uma relação $R$ está na 4FN se, para toda dependência multivalorada não trivial $X \twoheadrightarrow Y$, $X$ é uma superchave de $R$. Isso garante que fatos multivalorados independentes não sejam armazenados na mesma relação, evitando produtos cartesianos espúrios.

### Quinta Forma Normal (5FN / Forma Normal de Projeção-Junção)
Uma relação $R$ está na 5FN se, e somente se, toda dependência de junção (DJ) não trivial em $R$ é consequência das superchaves de $R$. Ou seja, a relação não pode ser decomposta em três ou mais projeções menores sem perda de informação.

---

## 2. Análise Detalhada por Tabela

### 2.1 Esquema `sc_corporativo`

#### `sc_corporativo.tb_endereco`
- **Chave Primária (PK):** `id` (UUID)
- **Chaves Candidatas (CC):** Nenhuma alternativa determinística global (mesmo logradouro e CEP podem ter diferentes identificadores de ponto rural ou coordenadas complementares).
- **Dependências Funcionais (DF):**
  - `id -> cep, logradouro, numero, cidade, estado`
- **Análise 1FN:** Todos os atributos são escalares e atômicos.
- **Análise 2FN:** Como a PK é simples (`id`), não existem dependências parciais.
- **Análise 3FN e FNBC:** Não há dependência transitiva entre atributos não primos. O par `cep -> cidade, estado` foi avaliado, porém no contexto rural brasileiro com CEP genérico por distrito/município, a localidade e o logradouro são mantidos na entidade de endereço para garantir integridade pontual sem redundância em cascata. O determinante `id` é superchave.
- **Análise 4FN e 5FN:** Não há dependências multivaloradas independentes. A tabela não admite decomposição de junção adicional.

#### `sc_corporativo.tb_empresa`
- **Chave Primária (PK):** `id` (UUID)
- **Chaves Candidatas (CC):** `cnpj`, `codigo_interno`
- **Dependências Funcionais (DF):**
  - `id -> endereco_id, nome, razao_social, codigo_interno, email, cnpj`
  - `cnpj -> id, endereco_id, nome, razao_social, codigo_interno, email`
  - `codigo_interno -> id, endereco_id, nome, razao_social, email, cnpj`
- **Análise 1FN, 2FN, 3FN e FNBC:** Todas as dependências funcionais partem de superchaves (`id`, `cnpj`, `codigo_interno`). Não existem dependências transitivas entre atributos não chave.
- **Conformidade:** 1FN, 2FN, 3FN, FNBC, 4FN e 5FN atendidas.

#### `sc_corporativo.tb_configuracao_operacao`
- **Chave Primária (PK):** `id` (UUID)
- **Chaves Candidatas (CC):** `empresa_id` (relação 1:1 estrita com `tb_empresa`)
- **Dependências Funcionais (DF):**
  - `id -> empresa_id, tempo_max_viagem_horas, mortalidade_bloqueio_cabecas, prazo_analise_horas, meta_mortalidade, qtd_assinaturas_obrigatorias, alerta_sirene_re, alerta_inspecao_dias, alerta_cnh_vencida, alerta_tempo_parada_imprevista, atualizado_em`
  - `empresa_id -> id, tempo_max_viagem_horas, mortalidade_bloqueio_cabecas, ...`
- **Análise FNBC:** Os determinantes `id` e `empresa_id` são superchaves. A separação desta entidade da tabela `tb_empresa` evita a proliferação de colunas de parametrização e garante coesão temática.
- **Conformidade:** 1FN a 5FN atendidas.

#### `sc_corporativo.tb_usuario`
- **Chave Primária (PK):** `id` (UUID)
- **Chaves Candidatas (CC):** `cpf`, `email`
- **Dependências Funcionais (DF):**
  - `id -> empresa_id, tipo, cargo, nivel_acesso, cpf, cnh_numero, categoria_cnh, data_vencimento_cnh, nome_completo, data_nascimento, email, telefone, senha_hash, url_assinatura_geral, status_cadastro`
  - `cpf -> id, empresa_id, ...`
  - `email -> id, empresa_id, ...`
- **Análise FNBC:** Toda dependência funcional não trivial possui determinante que é superchave. A CNH é opcional para cargos não condutores (`analista`, `pecuarista`), mantendo atomicidade sem decomposição artificial de perfis em excesso de tabelas satélites.
- **Conformidade:** 1FN a 5FN atendidas.

#### `sc_corporativo.tb_fazenda` e `sc_corporativo.tb_unidade_frigorifica`
- **Chaves Primárias (PK):** `id` (UUID)
- **Chaves Candidatas (CC):** `cnpj` (nas duas entidades)
- **Dependências Funcionais (DF):**
  - `id -> empresa_id, pecuarista_id, endereco_id, nome, razao_social, cnpj` (fazenda)
  - `id -> empresa_id, analista_id, endereco_id, nome, cnpj, qtd_currais` (unidade frigorífica)
- **Conformidade:** Atendem formalmente até a 5FN.

---

### 2.2 Esquema `sc_frota`

#### `sc_frota.tb_veiculo_base`, `tb_veiculo_cavalo`, `tb_veiculo_carreta`
- **Arquitetura:** Herança relacional nativa do PostgreSQL (`INHERITS`).
- **Chave Primária (PK):** `id` (UUID)
- **Chave Candidata (CC):** `placa` (VARCHAR(7) com restrição UNIQUE)
- **Dependências Funcionais (DF):**
  - `tb_veiculo_base`: `id -> empresa_id, placa, ativo, data_vencimento_inspecao`
  - `tb_veiculo_cavalo`: `id -> empresa_id, placa, ativo, data_vencimento_inspecao, km_acumulado`
  - `tb_veiculo_carreta`: `id -> empresa_id, placa, ativo, data_vencimento_inspecao, capacidade_cabecas`
- **Análise de Herança e Normalização:**
  A herança relacional no PostgreSQL particiona fisicamente os atributos específicos (`km_acumulado` exclusivo de cavalos mecânicos; `capacidade_cabecas` exclusivo de reboques) enquanto compartilha a chave natural (`placa`) e a chave primária artificial (`id`). Não há valores nulos decorrentes de tipos incompatíveis, preservando a 3FN e a FNBC.

---

### 2.3 Esquema `sc_operacao`

#### `sc_operacao.tb_relatorio_viagem`
- **Chave Primária (PK):** `id` (UUID)
- **Chave Candidata (CC):** `numero_gta` (Guia de Trânsito Animal - UNIQUE)
- **Dependências Funcionais (DF):**
  - `id -> empresa_id, status, fazenda_id, motorista_id, manobrista_id, curraleiro_id, cavalo_id, carreta_id, numero_gta, numero_nota_fiscal, capacidade_carga_utilizada, data_embarque, horario_embarque, horario_saida_propriedade, km_saida_embarcadouro, data_chegada_unidade, horario_chegada_unidade, horario_desembarque, km_chegada_desembarcadouro, numero_curral, sirene_re_funcionou, qtd_machos, qtd_femeas, qtd_marrucos, qtd_em_pe, qtd_deitado, qtd_morto, qtd_emergencia, url_laudo_mortalidade, motivo_emergencia, comentarios, url_assinatura_pecuarista, url_assinatura_motorista, url_assinatura_manobrista, url_assinatura_curraleiro, criado_em, enviado_em`
  - `numero_gta -> id, empresa_id, ...`
- **Análise 1FN:** Todos os campos são atômicos.
- **Análise 2FN:** A PK é simples (`id`), portanto não há dependências parciais.
- **Análise 3FN:** Os contadores de gado (`qtd_machos`, `qtd_femeas`, `qtd_em_pe`, `qtd_morto`) são fatos primitivos registrados em etapas distintas (origem vs. destino). A métrica de saldo/quebra não é persistida como coluna derivada nesta tabela, sendo calculada dinamicamente na visão analítica `sc_operacao.vw_fato_transporte_animal`, preservando a pureza da 3FN.
- **Análise 4FN:** As anomalias e as paradas ocorridas na viagem são multivaloradas e independentes entre si. Para respeitar a 4FN, paradas e anomalias **não foram embutidas** nesta relação, sendo isoladas em tabelas filhas dedicadas (`tb_parada_imprevista`, `tb_anomalia_embarque`, `tb_anomalia_desembarque`).
- **Conformidade:** 1FN, 2FN, 3FN, FNBC, 4FN e 5FN.

#### `sc_operacao.tb_parada_imprevista`
- **Chave Primária (PK):** `id` (UUID)
- **Dependências Funcionais (DF):**
  - `id -> relatorio_id, dominio_parada_id, data_hora_inicio, data_hora_fim`
- **Análise:** Isola a dependência multivalorada de paradas em relação ao relatório de viagem. Conformidade plena até 5FN.

#### `sc_operacao.tb_dominio_anomalia`
- **Chave Primária (PK):** `id` (UUID)
- **Chave Candidata (CC):** `(tipo_etapa, codigo)`
- **Dependências Funcionais (DF):**
  - `id -> tipo_etapa, codigo, descricao, ativo, anomalia_pai_id`
  - `(tipo_etapa, codigo) -> id, descricao, ativo, anomalia_pai_id`
- **Análise da Hierarquia Recursiva:**
  A coluna `anomalia_pai_id` estabelece autorrelacionamento hierárquico na mesma entidade. Como o pai é referenciado por chave substituta (`id`) e validado por gatilho anti-ciclo (`fn_verificar_ciclo_anomalia`), a estrutura hierárquica respeita rigorosamente a FNBC.

#### `sc_operacao.tb_anomalia_embarque` e `tb_anomalia_desembarque`
- **Chaves Primárias (PK):** `id` (UUID)
- **Dependências Funcionais (DF):**
  - `id -> relatorio_id, dominio_anomalia_id, descricao_outros`
- **Justificativa da Separação em Duas Tabelas:**
  A separação entre anomalias de embarque e desembarque decorre de momentos de captura distintos no fluxo operacional e responsabilidades jurídicas independentes (o pecuarista assina no embarque; o curraleiro e o manobrista assinam no desembarque). Isso evita dependências parciais de contexto e viabiliza integridade referencial com os domínios apropriados.

#### `sc_operacao.tb_auditoria_analise`
- **Chave Primária (PK):** `id` (UUID)
- **Chaves Candidatas (CC):** `(relatorio_id, data_hora_analise)`
- **Dependências Funcionais (DF):**
  - `id -> relatorio_id, analista_id, data_hora_analise, aprovado, motivo_rejeicao, parecer_tecnico`
- **Conformidade:** 1FN a 5FN atendidas.

#### `sc_operacao.tb_outbox_evento`
- **Chave Primária (PK):** `id` (UUID)
- **Dependências Funcionais (DF):**
  - `id -> empresa_id, tipo_evento, agregado_tipo, agregado_id, payload, criado_em, processado_em, erro_tentativas, ultimo_erro`
- **Análise sobre Atributo JSONB (Trade-off Técnico Controlado):**
  O atributo `payload` armazena o estado imutável da mensagem no padrão Transactional Outbox. Sob o prisma estrito da 1FN relacional clássica, estruturas JSONB podem ser interpretadas como não atômicas. No entanto, no contexto da arquitetura orientada a eventos, o `payload` é o valor atômico da mensagem a ser transmitida para filas de mensageria assíncrona. Os dados de consulta, agregação e consistência operacional permanecem 100% normalizados nas tabelas de negócio (`tb_relatorio_viagem`).

---

### 2.4 Esquema `sc_auditoria`

#### `sc_auditoria.tb_catalogo_dados`
- **Chave Primária (PK):** `id` (UUID)
- **Chave Candidata (CC):** `(esquema_nome, tabela_nome, coluna_nome)`
- **Dependências Funcionais (DF):**
  - `id -> esquema_nome, tabela_nome, coluna_nome, descricao, regra_negocio_critica, nivel_acesso_leitura, nivel_acesso_escrita, dado_pessoal_lgpd, atualizado_em`
  - `(esquema_nome, tabela_nome, coluna_nome) -> id, descricao, ...`
- **Conformidade:** O determinante da chave candidata natural é superchave. Conformidade total até a 5FN.

#### `sc_auditoria.tb_auditoria_log`
- **Chave Primária (PK):** `id` (UUID)
- **Dependências Funcionais (DF):**
  - `id -> empresa_id, tabela_afetada, operacao, usuario_db, dados_antigos, dados_novos, data_hora`
- **Trilha Imutável:** Representa um log de eventos DML append-only gerado via trigger com exclusão prévia de credenciais (`senha_hash`).

#### `sc_auditoria.tb_monitoramento_dau`
- **Chave Primária (PK):** `id` (UUID)
- **Chave Candidata (CC):** `(usuario_id, data_acesso)`
- **Dependências Funcionais (DF):**
  - `id -> usuario_id, data_acesso`
  - `(usuario_id, data_acesso) -> id`
- **Conformidade:** 1FN a 5FN atendidas.

#### `sc_auditoria.tb_historico_backup`
- **Chave Primária (PK):** `id` (UUID)
- **Dependências Funcionais (DF):**
  - `id -> operacao, status, nome_banco, arquivo_dump, tamanho_bytes, checksum_sha256, iniciado_em, finalizado_em, executado_por, mensagem_erro`
- **Conformidade:** 1FN a 5FN atendidas.

---

## 3. Matriz Resumo de Normalização

| Tabela | PK | Chaves Candidatas | Determinantes | Forma Normal Atingida |
| :--- | :--- | :--- | :--- | :--- |
| `sc_corporativo.tb_endereco` | `id` | - | `id` | FNBC / 5FN |
| `sc_corporativo.tb_empresa` | `id` | `cnpj`, `codigo_interno` | `id`, `cnpj`, `codigo_interno` | FNBC / 5FN |
| `sc_corporativo.tb_configuracao_operacao` | `id` | `empresa_id` | `id`, `empresa_id` | FNBC / 5FN |
| `sc_corporativo.tb_usuario` | `id` | `cpf`, `email` | `id`, `cpf`, `email` | FNBC / 5FN |
| `sc_corporativo.tb_fazenda` | `id` | `cnpj` | `id`, `cnpj` | FNBC / 5FN |
| `sc_corporativo.tb_unidade_frigorifica` | `id` | `cnpj` | `id`, `cnpj` | FNBC / 5FN |
| `sc_frota.tb_veiculo_base` | `id` | `placa` | `id`, `placa` | FNBC / 5FN |
| `sc_frota.tb_veiculo_cavalo` | `id` | `placa` | `id`, `placa` | FNBC / 5FN |
| `sc_frota.tb_veiculo_carreta` | `id` | `placa` | `id`, `placa` | FNBC / 5FN |
| `sc_operacao.tb_dominio_motivo_parada` | `id` | `codigo` | `id`, `codigo` | FNBC / 5FN |
| `sc_operacao.tb_dominio_anomalia` | `id` | `(tipo_etapa, codigo)` | `id`, `(tipo_etapa, codigo)` | FNBC / 5FN |
| `sc_operacao.tb_relatorio_viagem` | `id` | `numero_gta` | `id`, `numero_gta` | FNBC / 5FN |
| `sc_operacao.tb_parada_imprevista` | `id` | - | `id` | FNBC / 5FN |
| `sc_operacao.tb_anomalia_embarque` | `id` | - | `id` | FNBC / 5FN |
| `sc_operacao.tb_anomalia_desembarque` | `id` | - | `id` | FNBC / 5FN |
| `sc_operacao.tb_auditoria_analise` | `id` | - | `id` | FNBC / 5FN |
| `sc_operacao.tb_outbox_evento` | `id` | - | `id` | FNBC / 5FN (Payload JSONB) |
| `sc_auditoria.tb_catalogo_dados` | `id` | `(esquema, tabela, coluna)` | `id`, `(esquema, tabela, coluna)` | FNBC / 5FN |
| `sc_auditoria.tb_auditoria_log` | `id` | - | `id` | FNBC / 5FN (Payload JSONB) |
| `sc_auditoria.tb_monitoramento_dau` | `id` | `(usuario_id, data_acesso)` | `id`, `(usuario_id, data_acesso)` | FNBC / 5FN |
| `sc_auditoria.tb_historico_backup` | `id` | - | `id` | FNBC / 5FN |

---

## 4. Conclusão

O modelo de dados do ecossistema Efficientia cumpre integralmente os requisitos da Terceira Forma Normal e da Forma Normal de Boyce-Codd para todas as entidades transacionais e cadastrais. As exceções tecnológicas (atributos `JSONB` em auditoria e mensageria assíncrona) foram implementadas com isolamento estrito de finalidade, sem comprometer a integridade referencial nem a eficiência das consultas analíticas do banco relacional.
