-- ---------------------------------------------------
-- DATABASE WORKSPACE: INTROSPECÇÃO DO POSTGRESQL
-- Lê o catálogo do PostgreSQL (Efficientia-database) e devolve
-- um único JSON estruturado com tabelas, colunas, constraints,
-- índices, views, functions, procedures, triggers e catálogo de dados.
-- Uso: psql -X -A -t -q -f scripts/workspace/introspect.sql > catalog.json
-- ---------------------------------------------------

WITH
rel AS (
	SELECT c.oid, c.relname, c.relkind, n.nspname
	FROM pg_class c
	JOIN pg_namespace n ON n.oid = c.relnamespace
	WHERE n.nspname IN ('sc_corporativo', 'sc_frota', 'sc_operacao', 'sc_auditoria', 'sc_bi')
),
cat AS (
	SELECT cd.esquema_nome, cd.tabela_nome, cd.coluna_nome,
	       cd.descricao, cd.regra_negocio, cd.proprietario_dado, cd.classificacao_acesso,
	       cd.dado_pessoal_lgpd
	FROM sc_auditoria.tb_catalogo_dados cd
),
cols AS (
	SELECT r.oid,
		json_agg(json_build_object(
			'name', a.attname,
			'type', format_type(a.atttypid, a.atttypmod),
			'nullable', NOT a.attnotnull,
			'default', pg_get_expr(d.adbin, d.adrelid),
			'identity', NULLIF(a.attidentity, ''),
			'comment', col_description(r.oid, a.attnum),
			'description', c.descricao,
			'business_rule', c.regra_negocio,
			'personal', COALESCE(c.dado_pessoal_lgpd, false),
			'access_level', COALESCE(c.classificacao_acesso, 'INTERNAL')
		) ORDER BY a.attnum) AS columns
	FROM rel r
	JOIN pg_attribute a ON a.attrelid = r.oid AND a.attnum > 0 AND NOT a.attisdropped
	LEFT JOIN pg_attrdef d ON d.adrelid = r.oid AND d.adnum = a.attnum
	LEFT JOIN cat c ON c.esquema_nome = r.nspname AND c.tabela_nome = r.relname AND c.coluna_nome = a.attname
	GROUP BY r.oid
),
cons AS (
	SELECT r.oid,
		json_agg(json_build_object(
			'name', k.conname,
			'type', k.contype,
			'columns', (SELECT json_agg(a.attname ORDER BY u.ord) FROM unnest(k.conkey) WITH ORDINALITY u(attnum, ord)
				JOIN pg_attribute a ON a.attrelid = k.conrelid AND a.attnum = u.attnum),
			'ref_table', fr.relname,
			'ref_columns', (SELECT json_agg(a.attname ORDER BY u.ord) FROM unnest(k.confkey) WITH ORDINALITY u(attnum, ord)
				JOIN pg_attribute a ON a.attrelid = k.confrelid AND a.attnum = u.attnum),
			'on_delete', CASE k.confdeltype WHEN 'c' THEN 'CASCADE' WHEN 'n' THEN 'SET NULL' WHEN 'd' THEN 'SET DEFAULT' WHEN 'r' THEN 'RESTRICT' WHEN 'a' THEN 'NO ACTION' END,
			'on_update', CASE k.confupdtype WHEN 'c' THEN 'CASCADE' WHEN 'n' THEN 'SET NULL' WHEN 'd' THEN 'SET DEFAULT' WHEN 'r' THEN 'RESTRICT' WHEN 'a' THEN 'NO ACTION' END,
			'definition', pg_get_constraintdef(k.oid),
			'inherited', NOT k.conislocal
		) ORDER BY k.contype, k.conname) AS constraints
	FROM rel r
	JOIN pg_constraint k ON k.conrelid = r.oid
	LEFT JOIN pg_class fr ON fr.oid = k.confrelid
	GROUP BY r.oid
),
idx AS (
	SELECT i.indexrelid, i.indrelid, ic.relname AS name, t.relname AS table_name,
		am.amname AS method, i.indisunique AS is_unique, i.indisprimary AS is_primary,
		pg_get_indexdef(i.indexrelid) AS definition,
		pg_get_expr(i.indpred, i.indrelid) AS predicate,
		(SELECT json_agg(pg_get_indexdef(i.indexrelid, k, true) ORDER BY k) FROM generate_series(1, i.indnkeyatts) k) AS columns,
		EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conindid = i.indexrelid AND k.contype IN ('p', 'u')) AS from_constraint,
		obj_description(i.indexrelid, 'pg_class') AS comment
	FROM pg_index i
	JOIN pg_class ic ON ic.oid = i.indexrelid
	JOIN rel t ON t.oid = i.indrelid
	JOIN pg_am am ON am.oid = ic.relam
),
trg AS (
	SELECT t.tgname AS name, c.relname AS table_name, p.proname AS function_name,
		pg_get_triggerdef(t.oid) AS definition,
		CASE WHEN t.tgtype & 2 > 0 THEN 'BEFORE' WHEN t.tgtype & 64 > 0 THEN 'INSTEAD OF' ELSE 'AFTER' END AS timing,
		CASE WHEN t.tgtype & 1 > 0 THEN 'ROW' ELSE 'STATEMENT' END AS level,
		array_to_json(array_remove(ARRAY[
			CASE WHEN t.tgtype & 4 > 0 THEN 'INSERT' END,
			CASE WHEN t.tgtype & 16 > 0 THEN 'UPDATE' END,
			CASE WHEN t.tgtype & 8 > 0 THEN 'DELETE' END,
			CASE WHEN t.tgtype & 32 > 0 THEN 'TRUNCATE' END], NULL)) AS events,
		t.tgenabled <> 'D' AS enabled,
		obj_description(t.oid, 'pg_trigger') AS comment
	FROM pg_trigger t
	JOIN rel c ON c.oid = t.tgrelid
	JOIN pg_proc p ON p.oid = t.tgfoid
	WHERE NOT t.tgisinternal
),
routines AS (
	SELECT p.proname AS name,
		CASE p.prokind WHEN 'p' THEN 'procedure' WHEN 'f' THEN 'function' WHEN 'a' THEN 'aggregate' WHEN 'w' THEN 'window' END AS kind,
		pg_get_function_arguments(p.oid) AS arguments,
		CASE WHEN p.prokind = 'p' THEN NULL ELSE pg_get_function_result(p.oid) END AS returns,
		l.lanname AS language,
		CASE p.provolatile WHEN 'i' THEN 'IMMUTABLE' WHEN 's' THEN 'STABLE' ELSE 'VOLATILE' END AS volatility,
		p.prosecdef AS security_definer,
		p.prorettype = 'trigger'::regtype AS is_trigger_function,
		pg_get_functiondef(p.oid) AS definition,
		obj_description(p.oid, 'pg_proc') AS comment
	FROM pg_proc p
	JOIN pg_namespace n ON n.oid = p.pronamespace
	JOIN pg_language l ON l.oid = p.prolang
	WHERE n.nspname IN ('sc_corporativo', 'sc_frota', 'sc_operacao', 'sc_auditoria', 'sc_bi')
),
view_deps AS (
	SELECT v.oid, json_agg(DISTINCT t.relname) AS depends_on
	FROM rel v
	JOIN pg_rewrite rw ON rw.ev_class = v.oid
	JOIN pg_depend d ON d.objid = rw.oid AND d.classid = 'pg_rewrite'::regclass AND d.refclassid = 'pg_class'::regclass
	JOIN pg_class t ON t.oid = d.refobjid AND t.oid <> v.oid
	WHERE v.relkind IN ('v', 'm')
	GROUP BY v.oid
)
SELECT json_build_object(
	'generated_at', to_char(now() AT TIME ZONE 'America/Sao_Paulo', 'YYYY-MM-DD"T"HH24:MI:SS'),
	'server_version', current_setting('server_version'),
	'access_levels', json_build_array(
		json_build_object('code', 'PUBLIC', 'rank', 1, 'description', 'Dado de referência ou catálogo público.', 'audience', 'Aplicações cliente e dashboards.'),
		json_build_object('code', 'INTERNAL', 'rank', 2, 'description', 'Dado operacional de transporte e frotas.', 'audience', 'Usuários operacionais autenticados.'),
		json_build_object('code', 'RESTRICTED', 'rank', 3, 'description', 'Dado de viagem, conformidade ou pessoal (LGPD).', 'audience', 'Analistas veterinários e motoristas autorizados.'),
		json_build_object('code', 'CONFIDENTIAL', 'rank', 4, 'description', 'Credenciais, trilhas de auditoria e backups.', 'audience', 'DBA e administradores de segurança.')
	),
	'tables', (
		SELECT json_agg(json_build_object(
			'name', r.relname,
			'schema', r.nspname,
			'kind', CASE r.relkind WHEN 'p' THEN 'partitioned' ELSE 'table' END,
			'parent', (SELECT pc.relname FROM pg_inherits ih JOIN pg_class pc ON pc.oid = ih.inhparent WHERE ih.inhrelid = r.oid LIMIT 1),
			'children', (SELECT json_agg(cc.relname ORDER BY cc.relname) FROM pg_inherits ih JOIN pg_class cc ON cc.oid = ih.inhrelid WHERE ih.inhparent = r.oid),
			'comment', obj_description(r.oid, 'pg_class'),
			'columns', cols.columns,
			'constraints', COALESCE(cons.constraints, '[]'::json)
		) ORDER BY r.relname)
		FROM rel r
		LEFT JOIN cols ON cols.oid = r.oid
		LEFT JOIN cons ON cons.oid = r.oid
		WHERE r.relkind IN ('r', 'p')
	),
	'views', (
		SELECT json_agg(json_build_object(
			'name', r.relname,
			'schema', r.nspname,
			'materialized', r.relkind = 'm',
			'comment', obj_description(r.oid, 'pg_class'),
			'columns', cols.columns,
			'depends_on', COALESCE(vd.depends_on, '[]'::json),
			'definition', pg_get_viewdef(r.oid, true)
		) ORDER BY r.relname)
		FROM rel r
		LEFT JOIN cols ON cols.oid = r.oid
		LEFT JOIN view_deps vd ON vd.oid = r.oid
		WHERE r.relkind IN ('v', 'm')
	),
	'indexes', (SELECT json_agg(json_build_object(
		'name', name, 'table', table_name, 'method', method, 'unique', is_unique, 'primary', is_primary,
		'columns', columns, 'predicate', predicate, 'from_constraint', from_constraint,
		'definition', definition, 'comment', comment) ORDER BY table_name, name) FROM idx),
	'triggers', (SELECT json_agg(row_to_json(trg) ORDER BY table_name, name) FROM trg),
	'routines', (SELECT json_agg(row_to_json(routines) ORDER BY kind, name) FROM routines),
	'sequences', (
		SELECT json_agg(json_build_object('name', r.relname, 'owned_by', d.refobjid::regclass::text || '.' || a.attname) ORDER BY r.relname)
		FROM rel r
		LEFT JOIN pg_depend d ON d.objid = r.oid AND d.deptype IN ('a', 'i') AND d.refclassid = 'pg_class'::regclass
		LEFT JOIN pg_attribute a ON a.attrelid = d.refobjid AND a.attnum = d.refobjsubid
		WHERE r.relkind = 'S'
	)
);
