# Política de Backup e Recuperação de Desastres (Runbook Operacional)

Este documento define os procedimentos oficiais de cópia de segurança, auditoria de integridade e recuperação de desastres para a base de dados relacional do ecossistema Efficientia.

---

## 1. Classificação de Dados e Níveis de Serviço (RPO e RTO)

Os requisitos operacionais de recuperação são estruturados em três níveis de serviço (Tiers) baseados na criticidade das entidades de negócio:

| Nível (Tier) | Domínio de Dados | Tabelas Abrangidas | RPO Alvo (Ponto Máximo de Perda) | RTO Alvo (Tempo Máximo de Restauração) |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1** | **Transacional Crítico** | `tb_relatorio_viagem`, `tb_outbox_evento`, `tb_auditoria_analise`, `tb_parada_imprevista`, `tb_anomalia_*` | **RPO < 5 minutos** (via WAL archiving / replicação contínua) | **RTO < 1 hora** |
| **Tier 2** | **Cadastros Mestres e Parâmetros** | `tb_empresa`, `tb_configuracao_operacao`, `tb_usuario`, `tb_fazenda`, `tb_unidade_frigorifica`, `tb_veiculo_*` | **RPO < 24 horas** (via backup lógico diário) | **RTO < 4 horas** |
| **Tier 3** | **Histórico e Métricas** | `tb_auditoria_log`, `tb_monitoramento_dau`, `tb_catalogo_dados`, `tb_historico_backup` | **RPO < 24 horas** (via backup lógico diário) | **RTO < 8 horas** |

### Definições
- **RPO (Recovery Point Objective):** Volume temporal máximo de dados que a organização tolera perder entre a última cópia válida e o momento da falha.
- **RTO (Recovery Time Objective):** Tempo máximo tolerado para restabelecer a operação e disponibilizar os dados para as aplicações clientes.

---

## 2. Estratégia de Cópia de Segurança (Backup)

### Formato e Compactação
Os backups lógicos são gerados através da ferramenta nativa `pg_dump` utilizando o formato customizado (`--format=custom` / `-Fc`) com nível de compressão máximo (`--compress=9`). Esse formato inclui estrutura de índices, dados em blocos compactados e permite restauração paralela seletiva.

### Execução Automatizada
A rotina é disparada via script bash parametrizado:
```bash
./01_postgresql/08_backup/backup.sh
```

### Garantia de Integridade Criptográfica
Ao término da geração do arquivo `.dump`, o script calcula o resumo criptográfico SHA-256 e grava o arquivo de conferência `.sha256` correspondente. Qualquer alteração ou corrupção de bytes durante transferência é imediatamente identificada.

### Registro Automático no Histórico de Governança
Toda execução (com êxito ou falha) registra uma entrada em `sc_auditoria.tb_historico_backup` através da procedure `sc_auditoria.sp_registrar_evento_backup`, alimentando a visão de conformidade `sc_auditoria.vw_status_backups`.

---

## 3. Procedimento de Restauração Completa (Cold Restore)

### Pré-requisitos
1. Acesso administrativo (`superuser` ou papel proprietário das tabelas) ao servidor PostgreSQL.
2. Arquivo `.dump` e respectivo `.sha256` disponíveis em disco.

### Passo a Passo de Execução
1. Executar o script de restauração:
   ```bash
   ./01_postgresql/08_backup/restore.sh ./backups/efficientia_backup_20261029_020000.dump
   ```
2. O script executa automaticamente as seguintes etapas:
   - Valida o checksum SHA-256 do arquivo contra o arquivo `.sha256`.
   - Executa `pg_restore` com as flags `--clean` e `--if-exists`, garantindo recriação segura sem duplicidades.
   - Registra o evento de restauração em `sc_auditoria.tb_historico_backup`.
   - Executa a função `sc_auditoria.fn_contagem_linhas_tabelas()` para auditoria volumétrica imediata de todas as tabelas dos quatro esquemas.
3. Atualizar as visões materializadas do Data Mart:
   ```sql
   REFRESH MATERIALIZED VIEW sc_operacao.mv_analise_mortalidade_mensal;
   ```

---

## 4. Procedimento de Recuperação Cirúrgica em Nível de Linha (Surgical Recovery)

Em incidentes operacionais de modificação indevida ou deleção acidental de registros sem corrupção global da base, **não é necessário restaurar o dump completo**, evitando paradas no sistema.

A base relacional conta com a procedure de recuperação cirúrgica `sc_auditoria.sp_restaurar_registro_auditoria(p_log_id UUID)`, que lê o snapshot histórico imutável em JSONB registrado pela trigger de auditoria (`sc_auditoria.tb_auditoria_log`) e reconstrói o estado original da linha.

### Tabelas Habilitadas para Restauração Cirúrgica
- `sc_operacao.tb_relatorio_viagem`
- `sc_corporativo.tb_configuracao_operacao`
- `sc_corporativo.tb_usuario`
- `sc_corporativo.tb_empresa`

### Execução de Recuperação Cirúrgica
1. Localizar o identificador do log transacional na tabela de auditoria:
   ```sql
   SELECT id, tabela_afetada, operacao, usuario_db, data_hora, dados_antigos
   FROM sc_auditoria.tb_auditoria_log
   WHERE tabela_afetada = 'sc_operacao.tb_relatorio_viagem'
     AND operacao IN ('UPDATE', 'DELETE')
   ORDER BY data_hora DESC
   LIMIT 5;
   ```
2. Executar a chamada da procedure com o identificador UUID do log:
   ```sql
   CALL sc_auditoria.sp_restaurar_registro_auditoria('c9aa0000-0000-4000-8000-000000000001');
   ```
3. A procedure aplica o snapshot anterior via `jsonb_populate_record`, trata preservação de credenciais e registra a operação com o tipo `'RESTORE_AUDITORIA'` no histórico oficial de recuperação.

---

## 5. Monitoramento Contínuo de Conformidade de RPO

A conformidade com a janela de 24 horas pode ser verificada a qualquer momento através da visualização:
```sql
SELECT nome_banco, arquivo_dump, tamanho_mb, duracao_segundos,
       horas_desde_execucao, dentro_janela_rpo_24h, status
FROM sc_auditoria.vw_status_backups
ORDER BY iniciado_em DESC
LIMIT 5;
```
Se a coluna `dentro_janela_rpo_24h` for `FALSE` ou o último `status` for `FALHA`, um alerta operacional deve ser emitido para a equipe de infraestrutura.
