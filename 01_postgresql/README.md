# Camada Relacional (PostgreSQL / Supabase)

Este diretório contém todos os scripts DDL, DML, views analíticas e rotinas procedurais do banco de dados relacional principal do projeto Efficientia (hospedado no Supabase).

## Ordem de Execução dos Scripts

Para inicializar o banco de dados do zero, execute os diretórios na ordem numérica estrita abaixo:

1. **`01_ddl/`**: Criação de schemas (`sc_auditoria`, `sc_corporativo`, `sc_frota`, `sc_operacao`), tipos enumerados (ENUMs), tabelas de governança, corporativo, frota e transacionais.
2. **`02_constraints_and_indexes/`**: Criação de índices de isolamento multi-tenant, chaves estrangeiras e índices de performance em colunas de alta seletividade.
3. **`03_views/`**: Criação de dimensões (Star Schema), tabela fato (`vw_fato_transporte_animal`) e materialized views para análise de mortalidade.
4. **`04_functions/`**: Funções utilitárias e gatilhos de auditoria genérica, registro de DAU e validação de alocação de frota.
5. **`05_triggers/`**: Associação de triggers de auditoria nas tabelas críticas e validações operacionais pré-operação.
6. **`06_procedures/`**: Stored procedures transacionais para aprovação de relatórios de viagem e apontamento de anomalias com controle de concorrência.
7. **`07_dataload/`**: Carga de dados inicial do catálogo de dados (dicionário de dados e conformidade LGPD/RBAC).
8. **`08_migrations/`**: Migrações incrementais aplicadas a ambientes já existentes (ex: Supabase em produção/desenvolvimento) sem necessidade de recriar o banco do zero.

## Observações Importantes
- **Ambiente Já Inicializado (Supabase)**: Caso você já tenha rodado os scripts 01 a 07 anteriormente no seu Supabase, basta executar o script `08_migrations/01_correcoes_e_outbox_supabase.sql` no SQL Editor para aplicar as correções e adicionar a tabela de eventos da Outbox.
- **Pooler Supabase**: Para execuções via aplicações ou scripts externos, utilize a porta **5432** (Session Pooler) para suporte completo a transações (`BEGIN / COMMIT`).
- **Idempotência**: Scripts de procedures e views utilizam `CREATE OR REPLACE`. Os scripts DDL são transacionais (`BEGIN; ... COMMIT;`).
