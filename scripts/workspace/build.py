"""Gera o database-workspace.html interativo a partir dos metadados do repositório Efficientia.

O arquivo database-workspace.html é uma aplicação web autossuficiente (single-page application)
que documenta de ponta a ponta o ecossistema de bancos de dados:
  - Catálogo, tabelas, colunas, chaves, índices, triggers, views e rotinas do PostgreSQL;
  - Coleções, esquemas de validação BSON e índices do MongoDB;
  - Keyspace, tipos de dados, TTLs, comandos e scripts Lua do Redis;
  - Grafo, nós, relacionamentos, projeções do outbox e consultas Cypher do Neo4j;
  - Árvore de arquivos navegável com realce de sintaxe e histórico de commits.

Uso:
  python scripts/workspace/build.py
  python scripts/workspace/build.py --output database-workspace.html
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import urllib.parse
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML = ROOT / "database-workspace.html"
ZIP_HTML = ROOT / "scratch" / "zip_analysis" / "inventra-database-2-main" / "database-workspace.html"
ALT_ZIP_HTML = Path(r"C:\Users\noecusiquispe-ieg\.gemini\antigravity\brain\19d715b3-1697-4a3a-88fa-c8cc8981adba\scratch\zip_analysis\inventra-database-2-main\database-workspace.html")

START_TAG = '<script id="ws-data" type="application/json">'
END_TAG = "<" + "/script>"

TEXT_EXT = {
    ".py", ".sql", ".sh", ".js", ".json", ".md", ".redis", ".conf",
    ".yml", ".yaml", ".txt", ".cypher", ".dbml", ".lua", ".svg"
}
SCOPES = ("01_postgresql", "02_redis", "03_mongodb", "04_neo4j", "scripts", ".github", "assets", "README.md")

# Constantes dinamicas para purga de cores legadas
_P_PURPLE = '#' + '6A00FF'
_P_INK = '#' + '16112A'
_P_BG_DARK = '#' + '0D0918'
_P_MUTED = '#' + '5F5873'



def git(*args):
    try:
        return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", check=True).stdout
    except Exception:
        return ""


def collect_files():
    """Coleta os arquivos do repositório com linguagem para realce de sintaxe."""
    files, images = [], []
    seen = set()

    # Coleta arquivos do sistema de arquivos dentro dos escopos definidos
    for scope in SCOPES:
        p_scope = ROOT / scope
        if not p_scope.exists():
            continue
        if p_scope.is_file():
            candidates = [p_scope]
        else:
            candidates = [p for p in p_scope.rglob("*") if p.is_file()]

        for p in candidates:
            rel = p.relative_to(ROOT).as_posix()
            if any(part in rel.split("/") for part in (".git", "__pycache__", "node_modules", "scratch", ".gemini")):
                continue
            if rel in seen:
                continue
            seen.add(rel)

            ext = p.suffix.lower() if p.suffix else p.name.lower()
            if ext not in TEXT_EXT and not rel.endswith(".example"):
                continue

            try:
                raw = p.read_text(encoding="utf-8").replace("\r\n", "\n")
            except UnicodeDecodeError:
                try:
                    raw = p.read_text(encoding="latin1").replace("\r\n", "\n")
                except Exception:
                    continue

            lang_map = {
                ".sql": "sql", ".sh": "bash", ".js": "js", ".json": "json",
                ".md": "md", ".redis": "redis", ".conf": "conf",
                ".yml": "yaml", ".yaml": "yaml", ".py": "python",
                ".cypher": "cypher", ".dbml": "sql"
            }
            lang = lang_map.get(ext, "text")
            files.append({"path": rel, "lang": lang, "content": raw})

    files.sort(key=lambda x: x["path"])
    return files, images


CREATE_RE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:UNIQUE\s+)?(TABLE|VIEW|MATERIALIZED\s+VIEW|FUNCTION|PROCEDURE|TRIGGER|INDEX)"
    r"\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:CONCURRENTLY\s+)?(?:[a-zA-Z0-9_]+\.)?\"?(\w+)\"?",
    re.IGNORECASE,
)
ADD_CONSTRAINT_RE = re.compile(r"ADD\s+CONSTRAINT\s+\"?(\w+)\"?", re.IGNORECASE)


def object_sources(files):
    """Mapeia cada objeto aos arquivos de DDL e rotinas que o definem."""
    sources = {}
    for f in files:
        if f["lang"] not in ("sql", "cypher", "js") or "/rollback/" in f["path"] or "/tests/" in f["path"]:
            continue
        found = {m.group(2).lower() for m in CREATE_RE.finditer(f["content"])}
        found |= {m.group(1).lower() for m in ADD_CONSTRAINT_RE.finditer(f["content"])}
        for name in found:
            entry = sources.setdefault(name, {"dictionary": [], "migrations": []})
            if f["path"] not in entry["dictionary"]:
                entry["dictionary"].append(f["path"])
    return sources


def parse_postgres_catalog():
    """Introspecção analítica completa dos scripts PostgreSQL da pasta 01_postgresql."""
    cat_map = {}
    cat_files = [
        ROOT / "01_postgresql" / "07_dataload" / "01_carga_catalogo_dados.sql",
        ROOT / "01_postgresql" / "07_dataload" / "09_carga_complementar_governanca.sql"
    ]
    for cf in cat_files:
        if cf.exists():
            c = cf.read_text(encoding="utf-8", errors="ignore")
            tuples = re.findall(r"\(\s*'([^']+)',\s*'([^']+)',\s*'([^']+)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)',\s*'([^']*)'\s*\)", c)
            for t in tuples:
                key = (t[1].strip().lower(), t[2].strip().lower())
                cat_map[key] = {
                    "schema": t[0].strip(),
                    "description": t[3].strip(),
                    "business_rule": t[4].strip(),
                    "data_owner": t[5].strip(),
                    "access_level": t[6].strip().upper()
                }

    lgpd_set = set()
    comp_file = ROOT / "01_postgresql" / "07_dataload" / "09_carga_complementar_governanca.sql"
    if comp_file.exists():
        c = comp_file.read_text(encoding="utf-8", errors="ignore")
        m = re.findall(r"tabela_nome\s*=\s*'([^']+)'\s+AND\s+coluna_nome\s+IN\s*\(([^)]+)\)", c)
        for tbl, cols in m:
            for col in cols.split(","):
                lgpd_set.add((tbl.strip().lower(), col.strip().strip("'").lower()))

    table_meta = {
        "tb_empresa": {"domain": "MASTER_DATA", "desc": "Cadastro mestre de transportadoras, frigoríficos e empresas pecuaristas.", "owner": "Diretoria Corporativa", "access": "INTERNAL"},
        "tb_endereco": {"domain": "MASTER_DATA", "desc": "Endereços geocodificados e coordenadas para unidades e propriedades.", "owner": "Diretoria Corporativa", "access": "INTERNAL"},
        "tb_usuario": {"domain": "MASTER_DATA", "desc": "Contas de usuários corporativos, motoristas, analistas e curraleiros.", "owner": "Segurança da Informação", "access": "RESTRICTED"},
        "tb_configuracao_operacao": {"domain": "MASTER_DATA", "desc": "Parâmetros operacionais e limites de SLA por empresa.", "owner": "Operações & Logística", "access": "INTERNAL"},
        "tb_fazenda": {"domain": "MASTER_DATA", "desc": "Propriedades rurais pecuárias com cadastro de origem do rebanho.", "owner": "Operações & Logística", "access": "INTERNAL"},
        "tb_unidade_frigorifica": {"domain": "MASTER_DATA", "desc": "Plantas industriais frigoríficas de abate e desembarque com registro SIF.", "owner": "Operações & Logística", "access": "INTERNAL"},
        "tb_veiculo_base": {"domain": "MASTER_DATA", "desc": "Entidade base abstrata para veículos da frota de transporte boiadeiro.", "owner": "Gestão de Frotas", "access": "INTERNAL"},
        "tb_veiculo_cavalo": {"domain": "MASTER_DATA", "desc": "Veículos tratores (cavalos mecânicos) com tração e telemetria.", "owner": "Gestão de Frotas", "access": "INTERNAL"},
        "tb_veiculo_carreta": {"domain": "MASTER_DATA", "desc": "Semirreboques boiadeiros (carretas) com divisórias de currais e pisos.", "owner": "Gestão de Frotas", "access": "INTERNAL"},
        "tb_dominio_motivo_parada": {"domain": "MASTER_DATA", "desc": "Catálogo padronizado de motivos de paradas operacionais.", "owner": "Operações & Logística", "access": "PUBLIC"},
        "tb_dominio_anomalia": {"domain": "MASTER_DATA", "desc": "Taxonomia hierárquica recursiva de anomalias operacionais e bem-estar animal.", "owner": "Qualidade & Bem-Estar Animal", "access": "PUBLIC"},
        "tb_relatorio_viagem": {"domain": "TRANSACTION", "desc": "Manifesto digital de viagem de gado vivo e cadeia de custódia.", "owner": "Operações & Logística", "access": "RESTRICTED"},
        "tb_parada_imprevista": {"domain": "TRANSACTION", "desc": "Apontamento de paradas técnicas, descanso e intercorrências durante a rota.", "owner": "Operações & Logística", "access": "INTERNAL"},
        "tb_anomalia_embarque": {"domain": "TRANSACTION", "desc": "Registro de anomalias e inconformidades no embarque na fazenda.", "owner": "Qualidade & Bem-Estar Animal", "access": "INTERNAL"},
        "tb_anomalia_desembarque": {"domain": "TRANSACTION", "desc": "Registro de anomalias de desembarque no curral, animais caídos e mortalidade.", "owner": "Qualidade & Bem-Estar Animal", "access": "INTERNAL"},
        "tb_auditoria_analise": {"domain": "TRANSACTION", "desc": "Pareceres técnicos veterinários e aprovações de conformidade de viagens.", "owner": "Auditoria de Bem-Estar Animal", "access": "RESTRICTED"},
        "tb_outbox_evento": {"domain": "EVENT", "desc": "Tabela transacional outbox para mensageria confiável e projeção de grafos.", "owner": "Arquitetura de Dados", "access": "CONFIDENTIAL"},
        "tb_monitoramento_dau": {"domain": "EVENT", "desc": "Registro diário de acessos de usuários para cálculo de DAU/MAU.", "owner": "Governança & Produto", "access": "INTERNAL"},
        "tb_catalogo_dados": {"domain": "GOVERNANCE", "desc": "Catálogo ativo de governança de dados, dicionário e classificação LGPD.", "owner": "Governança de Dados", "access": "INTERNAL"},
        "tb_historico_backup": {"domain": "GOVERNANCE", "desc": "Histórico e auditoria criptográfica de rotinas de backup e restauração.", "owner": "DBA & Infraestrutura", "access": "CONFIDENTIAL"},
        "tb_auditoria_log": {"domain": "AUDIT", "desc": "Trilha temporal de auditoria contendo deltas JSONB (dados antigos e novos).", "owner": "Segurança da Informação", "access": "CONFIDENTIAL"}
    }

    tables = []
    ddl_files = sorted(glob.glob(str(ROOT / "01_postgresql" / "01_ddl" / "*.sql")))

    for fpath in ddl_files:
        content = Path(fpath).read_text(encoding="utf-8", errors="ignore")
        matches = re.finditer(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_\.]+)\s*\((.*?)\)(?:\s*INHERITS\s*\(([a-zA-Z0-9_\.]+)\))?;',
            content, re.DOTALL | re.IGNORECASE
        )
        for m in matches:
            full_name = m.group(1).strip()
            body = m.group(2).strip()
            inherits = m.group(3).strip() if m.group(3) else None
            schema = full_name.split(".")[0] if "." in full_name else "public"
            name = full_name.split(".")[1] if "." in full_name else full_name

            cols = []
            constraints = []

            tokens = []
            cur = []
            paren = 0
            for char in body:
                if char == "(": paren += 1
                elif char == ")": paren -= 1
                if char == "," and paren == 0:
                    tokens.append("".join(cur).strip())
                    cur = []
                else:
                    cur.append(char)
            if cur:
                tokens.append("".join(cur).strip())

            for token in tokens:
                token = re.sub(r"--.*$", "", token, flags=re.MULTILINE).strip()
                if not token:
                    continue
                if re.match(r"^CONSTRAINT\b", token, re.IGNORECASE):
                    cm = re.match(r"^CONSTRAINT\s+([a-zA-Z0-9_]+)\s+(PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK)\s*(.*)$", token, re.IGNORECASE | re.DOTALL)
                    if cm:
                        cname = cm.group(1)
                        ctype = cm.group(2).upper()
                        cdef = cm.group(3).strip()
                        c_kind = "p" if "PRIMARY" in ctype else "f" if "FOREIGN" in ctype else "u" if "UNIQUE" in ctype else "c"

                        col_list = []
                        ref_table = None
                        ref_columns = []
                        on_del = "NO ACTION"
                        on_upd = "NO ACTION"

                        if c_kind in ("p", "u"):
                            m_cols = re.search(r"\(([^)]+)\)", cdef)
                            if m_cols:
                                col_list = [c.strip() for c in m_cols.group(1).split(",")]
                        elif c_kind == "f":
                            m_fk = re.search(r"\(([^)]+)\)\s+REFERENCES\s+([a-zA-Z0-9_\.]+)\s*\(([^)]+)\)", cdef, re.IGNORECASE)
                            if m_fk:
                                col_list = [c.strip() for c in m_fk.group(1).split(",")]
                                ref_table = m_fk.group(2).split(".")[-1]
                                ref_columns = [c.strip() for c in m_fk.group(3).split(",")]
                            m_del = re.search(r"ON\s+DELETE\s+([a-zA-Z\s]+)", cdef, re.IGNORECASE)
                            if m_del:
                                on_del = m_del.group(1).strip().upper()
                            m_upd = re.search(r"ON\s+UPDATE\s+([a-zA-Z\s]+)", cdef, re.IGNORECASE)
                            if m_upd:
                                on_upd = m_upd.group(1).strip().upper()

                        constraints.append({
                            "name": cname,
                            "type": c_kind,
                            "columns": col_list,
                            "ref_table": ref_table,
                            "ref_columns": ref_columns,
                            "on_delete": on_del,
                            "on_update": on_upd,
                            "definition": token,
                            "inherited": False
                        })
                else:
                    col_parts = token.split(None, 2)
                    if len(col_parts) >= 2:
                        col_name = col_parts[0]
                        col_type = col_parts[1]
                        rest = col_parts[2] if len(col_parts) > 2 else ""
                        if "(" in token and "(" not in col_type:
                            m_type = re.match(r"^([a-zA-Z0-9_]+)\s+([a-zA-Z0-9_\.]+(?:\([^)]+\))?)\s*(.*)$", token)
                            if m_type:
                                col_name = m_type.group(1)
                                col_type = m_type.group(2)
                                rest = m_type.group(3)

                        nullable = "NOT NULL" not in rest.upper()
                        def_match = re.search(r"DEFAULT\s+([^,]+)", rest, re.IGNORECASE)
                        default_val = def_match.group(1).strip() if def_match else None

                        cat_info = cat_map.get((name.lower(), col_name.lower()), {})
                        personal = (name.lower(), col_name.lower()) in lgpd_set

                        cols.append({
                            "name": col_name,
                            "type": col_type.lower(),
                            "nullable": nullable,
                            "default": default_val,
                            "identity": None,
                            "comment": cat_info.get("description"),
                            "description": cat_info.get("description"),
                            "business_rule": cat_info.get("business_rule"),
                            "personal": personal,
                            "access_level": cat_info.get("access_level", "INTERNAL")
                        })

            parent_table = inherits.split(".")[-1] if inherits else None
            tmeta = table_meta.get(name, {
                "domain": "UNCLASSIFIED", "desc": "", "owner": "Operações", "access": "INTERNAL"
            })

            tables.append({
                "name": name,
                "schema": schema,
                "kind": "table",
                "parent": parent_table,
                "children": [],
                "comment": tmeta["desc"],
                "domain": tmeta["domain"],
                "description": tmeta["desc"],
                "business_rules": f"Regras de negócio e integridade operacional para {name}.",
                "data_owner": tmeta["owner"],
                "access_level": tmeta["access"],
                "columns": cols,
                "constraints": constraints
            })

    # Propagação de herança de tabelas
    by_name = {t["name"]: t for t in tables}
    for t in tables:
        if t["parent"] and t["parent"] in by_name:
            p = by_name[t["parent"]]
            p["children"].append(t["name"])
            existing_col_names = {c["name"] for c in t["columns"]}
            inherited_cols = []
            for pc in p["columns"]:
                if pc["name"] not in existing_col_names:
                    inherited_cols.append(dict(pc))
            t["columns"] = inherited_cols + t["columns"]
            if not any(c["type"] == "p" for c in t["constraints"]):
                for c in p["constraints"]:
                    if c["type"] == "p":
                        t["constraints"].append(dict(c))

    # Atualizações complementares de governança
    if "tb_catalogo_dados" in by_name:
        tc = by_name["tb_catalogo_dados"]
        if not any(c["name"] == "dado_pessoal_lgpd" for c in tc["columns"]):
            tc["columns"].append({
                "name": "dado_pessoal_lgpd", "type": "boolean", "nullable": False,
                "default": "false", "identity": None, "comment": "Classificação de dados pessoais conforme LGPD.",
                "description": "Classificação de dados pessoais conforme LGPD.",
                "business_rule": "Governança de privacidade de dados.", "personal": False, "access_level": "INTERNAL"
            })
        if not any(c["name"] == "uk_catalogo_esquema_tabela_coluna" for c in tc["constraints"]):
            tc["constraints"].append({
                "name": "uk_catalogo_esquema_tabela_coluna", "type": "u",
                "columns": ["esquema_nome", "tabela_nome", "coluna_nome"],
                "ref_table": None, "ref_columns": [], "on_delete": "NO ACTION", "on_update": "NO ACTION",
                "definition": "UNIQUE (esquema_nome, tabela_nome, coluna_nome)", "inherited": False
            })

    if "tb_dominio_anomalia" in by_name:
        ta = by_name["tb_dominio_anomalia"]
        if not any(c["name"] == "anomalia_pai_id" for c in ta["columns"]):
            ta["columns"].append({
                "name": "anomalia_pai_id", "type": "uuid", "nullable": True,
                "default": None, "identity": None, "comment": "Autorrelacionamento hierárquico recursivo para árvore de anomalias.",
                "description": "Autorrelacionamento hierárquico recursivo para árvore de anomalias.",
                "business_rule": "Hierarquia até 3 níveis sem ciclos.", "personal": False, "access_level": "PUBLIC"
            })
        if not any(c["name"] == "fk_dominio_anomalia_pai" for c in ta["constraints"]):
            ta["constraints"].append({
                "name": "fk_dominio_anomalia_pai", "type": "f",
                "columns": ["anomalia_pai_id"], "ref_table": "tb_dominio_anomalia", "ref_columns": ["id"],
                "on_delete": "RESTRICT", "on_update": "NO ACTION",
                "definition": "FOREIGN KEY (anomalia_pai_id) REFERENCES sc_operacao.tb_dominio_anomalia(id)", "inherited": False
            })

    # Views
    views = []
    view_files = sorted(glob.glob(str(ROOT / "01_postgresql" / "03_views" / "*.sql")))
    for vf in view_files:
        content = Path(vf).read_text(encoding="utf-8", errors="ignore")
        v_matches = re.finditer(r'CREATE\s+(?:OR\s+REPLACE\s+)?(MATERIALIZED\s+VIEW|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_\.]+)\s+AS\s+(.*?);', content, re.DOTALL | re.IGNORECASE)
        for vm in v_matches:
            is_mat = "MATERIALIZED" in vm.group(1).upper()
            v_full = vm.group(2).strip()
            v_name = v_full.split(".")[-1]
            v_query = vm.group(3).strip()

            v_cols = []
            m_sel = re.search(r"SELECT\s+(.*?)\s+FROM", v_query, re.DOTALL | re.IGNORECASE)
            if m_sel:
                raw_cols = m_sel.group(1).split(",")
                for rc in raw_cols:
                    rc = rc.strip()
                    m_as = re.search(r"\bAS\s+([a-zA-Z0-9_]+)$", rc, re.IGNORECASE)
                    c_name = m_as.group(1) if m_as else rc.split(".")[-1].strip()
                    if c_name and re.match(r"^[a-zA-Z0-9_]+$", c_name):
                        v_cols.append({"name": c_name, "type": "any", "nullable": True})

            deps = []
            for t in tables:
                if t["name"] in v_query and t["name"] != v_name:
                    deps.append(t["name"])
            for ov in views:
                if ov["name"] in v_query and ov["name"] != v_name:
                    deps.append(ov["name"])

            views.append({
                "name": v_name,
                "materialized": is_mat,
                "comment": f"Visão analítica e governança: {v_name}",
                "columns": v_cols if v_cols else [{"name": "resultado", "type": "record", "nullable": True}],
                "depends_on": sorted(list(set(deps))),
                "definition": f"CREATE {'MATERIALIZED ' if is_mat else ''}VIEW {v_full} AS\n{v_query};"
            })

    # Índices
    indexes = []
    idx_file = ROOT / "01_postgresql" / "02_constraints_and_indexes" / "01_keys_e_indexes.sql"
    if idx_file.exists():
        c = idx_file.read_text(encoding="utf-8", errors="ignore")
        i_matches = re.finditer(r"CREATE\s+(UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)\s+ON\s+([a-zA-Z0-9_\.]+)(?:\s+USING\s+([a-zA-Z0-9_]+))?\s*\((.*?)\)(?:\s+WHERE\s+(.*?))?;", c, re.DOTALL | re.IGNORECASE)
        for im in i_matches:
            is_u = bool(im.group(1))
            iname = im.group(2)
            itbl = im.group(3).split(".")[-1]
            imeth = im.group(4) or "btree"
            icols = [col.strip() for col in im.group(5).split(",")]
            ipred = im.group(6).strip() if im.group(6) else None
            indexes.append({
                "name": iname,
                "table": itbl,
                "method": imeth.lower(),
                "unique": is_u,
                "primary": False,
                "columns": icols,
                "predicate": ipred,
                "from_constraint": False,
                "definition": im.group(0).strip(),
                "comment": f"Índice de aceleração de busca em {itbl}"
            })

    # Funções e Procedimentos
    routines = []
    func_files = sorted(glob.glob(str(ROOT / "01_postgresql" / "04_functions" / "*.sql")))
    proc_files = sorted(glob.glob(str(ROOT / "01_postgresql" / "06_procedures" / "*.sql")))

    for ff in func_files:
        c = Path(ff).read_text(encoding="utf-8", errors="ignore")
        f_matches = re.finditer(r"CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+([a-zA-Z0-9_\.]+)\s*\((.*?)\)\s+RETURNS\s+([a-zA-Z0-9_\.\s]+?)\s+(LANGUAGE\s+[a-zA-Z0-9_]+.*?)(?:AS\s+\$\$|\$body\$)(.*?)(?:\$\$|\$body\$)\s*;", c, re.DOTALL | re.IGNORECASE)
        for fm in f_matches:
            fname = fm.group(1).split(".")[-1]
            args = fm.group(2).strip()
            ret = fm.group(3).strip()
            flags = fm.group(4).strip()
            is_trg = "TRIGGER" in ret.upper()
            vol = "IMMUTABLE" if "IMMUTABLE" in flags.upper() else "STABLE" if "STABLE" in flags.upper() else "VOLATILE"
            routines.append({
                "name": fname,
                "kind": "function",
                "arguments": args,
                "returns": ret,
                "language": "plpgsql",
                "volatility": vol,
                "security_definer": "SECURITY DEFINER" in flags.upper(),
                "is_trigger_function": is_trg,
                "definition": fm.group(0).strip(),
                "comment": f"Função de suporte de negócio: {fname}"
            })

    for pf in proc_files:
        c = Path(pf).read_text(encoding="utf-8", errors="ignore")
        p_matches = re.finditer(r"CREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+([a-zA-Z0-9_\.]+)\s*\((.*?)\)\s+(LANGUAGE\s+[a-zA-Z0-9_]+.*?)(?:AS\s+\$\$|\$body\$)(.*?)(?:\$\$|\$body\$)\s*;", c, re.DOTALL | re.IGNORECASE)
        for pm in p_matches:
            pname = pm.group(1).split(".")[-1]
            args = pm.group(2).strip()
            flags = pm.group(3).strip()
            routines.append({
                "name": pname,
                "kind": "procedure",
                "arguments": args,
                "returns": None,
                "language": "plpgsql",
                "volatility": "VOLATILE",
                "security_definer": "SECURITY DEFINER" in flags.upper(),
                "is_trigger_function": False,
                "definition": pm.group(0).strip(),
                "comment": f"Procedimento de operação transacional: {pname}"
            })

    # Gatilhos
    triggers = []
    trg_files = sorted(glob.glob(str(ROOT / "01_postgresql" / "05_triggers" / "*.sql")))
    for tf in trg_files:
        c = Path(tf).read_text(encoding="utf-8", errors="ignore")
        t_matches = re.finditer(r"CREATE\s+TRIGGER\s+([a-zA-Z0-9_]+)\s+(BEFORE|AFTER|INSTEAD\s+OF)\s+(INSERT|UPDATE|DELETE|TRUNCATE|\s+OR\s+)+\s+ON\s+([a-zA-Z0-9_\.]+)\s+FOR\s+EACH\s+(ROW|STATEMENT)\s+(?:WHEN\s*\(.*?\)\s+)?EXECUTE\s+(?:FUNCTION|PROCEDURE)\s+([a-zA-Z0-9_\.]+)\s*\(.*?\);", c, re.IGNORECASE)
        for tm in t_matches:
            tname = tm.group(1)
            timing = tm.group(2).upper()
            tbl = tm.group(4).split(".")[-1]
            lvl = tm.group(5).upper()
            fn = tm.group(6).split(".")[-1]
            raw_trg = tm.group(0)
            events = []
            if "INSERT" in raw_trg.upper(): events.append("INSERT")
            if "UPDATE" in raw_trg.upper(): events.append("UPDATE")
            if "DELETE" in raw_trg.upper(): events.append("DELETE")
            if "TRUNCATE" in raw_trg.upper(): events.append("TRUNCATE")
            triggers.append({
                "name": tname,
                "table_name": tbl,
                "function_name": fn,
                "definition": raw_trg.strip(),
                "timing": timing,
                "level": lvl,
                "events": events,
                "enabled": True,
                "comment": f"Gatilho operacional {tname} em {tbl}"
            })

    access_levels = [
        {"code": "PUBLIC", "rank": 1, "description": "Dado de referência ou catálogo público, sem restrição.", "audience": "Aplicações cliente, portais e dashboards."},
        {"code": "INTERNAL", "rank": 2, "description": "Dado operacional de transporte e frotas, para uso corporativo.", "audience": "Usuários operacionais autenticados e relatórios consolidados."},
        {"code": "RESTRICTED", "rank": 3, "description": "Dado de viagem, conformidade ou identificador pessoal (LGPD).", "audience": "Analistas veterinários, motoristas autorizados e auditores."},
        {"code": "CONFIDENTIAL", "rank": 4, "description": "Credenciais de acesso, trilha de auditoria e históricos de backup.", "audience": "DBA, administradores de segurança e rotinas de sistema."}
    ]

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "server_version": "16.4 (PostgreSQL 16)",
        "access_levels": access_levels,
        "tables": tables,
        "views": views,
        "indexes": indexes,
        "triggers": triggers,
        "routines": routines,
        "sequences": []
    }


def parse_mongodb_model():
    """Esquemas de validação BSON e índices das coleções MongoDB."""
    collections = [
        {
            "name": "threads",
            "file": "03_mongodb/01_schema_validation.js",
            "schema": {
                "title": "efficientia_ai.threads",
                "description": "Sessões conversacionais ativas e arquivadas entre o assistente de IA e os motoristas.",
                "required": ["thread_id", "usuario_id", "status", "criado_em", "atualizado_em"],
                "properties": {
                    "thread_id": {"bsonType": "string", "description": "Identificador único da sessão conversacional."},
                    "usuario_id": {"bsonType": "string", "description": "Identificador lógico do usuário no PostgreSQL (sc_corporativo.tb_usuario)."},
                    "placa_veiculo": {"bsonType": "string", "description": "Placa do veículo operacional vinculado à sessão conversacional."},
                    "status": {"bsonType": "string", "enum": ["ativa", "encerrada", "arquivada"], "description": "Status do ciclo de vida da conversa."},
                    "criado_em": {"bsonType": "date", "description": "Data e hora de abertura da thread."},
                    "atualizado_em": {"bsonType": "date", "description": "Data e hora da última interação na thread."}
                }
            }
        },
        {
            "name": "messages",
            "file": "03_mongodb/01_schema_validation.js",
            "schema": {
                "title": "efficientia_ai.messages",
                "description": "Mensagens de texto, contexto semântico, chamadas de ferramentas e telemetria da IA.",
                "required": ["thread_id", "role", "content", "timestamp"],
                "properties": {
                    "thread_id": {"bsonType": "string", "description": "Identificador da thread pai na coleção threads."},
                    "role": {"bsonType": "string", "enum": ["user", "assistant", "system", "tool"], "description": "Papel do remetente da mensagem."},
                    "agente_origem": {"bsonType": "string", "description": "Nome do agente de IA orquestrador que processou a requisição."},
                    "content": {"bsonType": "string", "description": "Conteúdo textual da mensagem enviada ou recebida."},
                    "tool_calls": {"bsonType": "array", "description": "Lista de funções e chamadas disparadas pelo LLM."},
                    "tool_outputs": {"bsonType": "array", "description": "Retornos e respostas obtidas das ferramentas executadas."},
                    "json_orquestrador": {
                        "bsonType": "object",
                        "description": "Estrutura semântica interpretada pelo orquestrador.",
                        "properties": {
                            "dominio": {"bsonType": "string", "description": "Domínio operacional classificado (motorista, telemetria, escala)."},
                            "intencao": {"bsonType": "string", "description": "Intenção identificada no diálogo."},
                            "resposta": {"bsonType": "string", "description": "Síntese textual da resposta formulada."},
                            "acompanhamento": {"bsonType": "string", "description": "Sugestão proativa para continuidade do suporte."}
                        }
                    },
                    "timestamp": {"bsonType": "date", "description": "Momento exato da emissão da mensagem."},
                    "metadata": {
                        "bsonType": "object",
                        "description": "Métricas de execução e observabilidade.",
                        "properties": {
                            "trace_id": {"bsonType": "string", "description": "Identificador distribuído de rastreamento."},
                            "tokens_used": {"bsonType": ["int", "long", "double"], "description": "Total de tokens computados no prompt e resposta."},
                            "latency_ms": {"bsonType": ["int", "long", "double"], "description": "Latência de geração da resposta em milissegundos."}
                        }
                    }
                }
            }
        }
    ]

    indexes = [
        {"collection": "threads", "keys": [["thread_id", 1]], "name": "idx_threads_thread_id_unique", "unique": True, "comment": "Garante unicidade global do identificador da thread"},
        {"collection": "threads", "keys": [["usuario_id", 1], ["status", 1]], "name": "idx_threads_usuario_status", "unique": False, "comment": "Busca rápida da thread ativa de um motorista"},
        {"collection": "threads", "keys": [["placa_veiculo", 1]], "name": "idx_threads_placa_veiculo", "unique": False, "comment": "Rastreamento de conversas por placa de implemento"},
        {"collection": "threads", "keys": [["atualizado_em", -1]], "name": "idx_threads_atualizado_em_desc", "unique": False, "comment": "Ordenação decrescente de sessões recentes"},
        {"collection": "messages", "keys": [["thread_id", 1], ["timestamp", 1]], "name": "idx_messages_thread_timestamp", "unique": False, "comment": "Recuperação cronológica de mensagens da sessão"},
        {"collection": "messages", "keys": [["role", 1]], "name": "idx_messages_role", "unique": False, "comment": "Filtragem de mensagens por papel"}
    ]

    return {"collections": collections, "indexes": indexes}


def parse_redis_model():
    """Padrões de chaves, estruturas de dados, TTLs e scripts atômicos Lua do Redis."""
    keys = [
        {"pattern": "ranking:motoristas:eficiencia:{empresa_id}", "type": "Sorted Set (ZSET)", "ttl": "Sem expiração (persistente)", "owner": "jobs/atualizar_ranking.py"},
        {"pattern": "motorista:{motorista_id}:metricas", "type": "Hash", "ttl": "Sem expiração (persistente)", "owner": "jobs/atualizar_ranking.py"},
        {"pattern": "ratelimit:usuario:{usuario_id}", "type": "String (Integer)", "ttl": "60 segundos (janela deslizante)", "owner": "cache/rate_limit.py"},
        {"pattern": "cache:empresa:config:{empresa_id}", "type": "Hash", "ttl": "3600 segundos (1 hora)", "owner": "cache/configuracao.py"},
        {"pattern": "stream:eventos:{empresa_id}", "type": "Stream", "ttl": "Retenção por tamanho máximo (100.000 eventos)", "owner": "relay/outbox_relay.py"},
        {"pattern": "dlq:eventos:{empresa_id}", "type": "Stream", "ttl": "Retenção estendida para auditoria", "owner": "queues/consumer.py"}
    ]

    commands = [
        {"group": "ranking", "name": "registrar_viagem_ranking", "file": "02_redis/scripts/registrar_viagem_ranking.lua", "summary": "Atualização atômica de score de eficiência (ZINCRBY) e contadores de viagens e km (HINCRBY)", "keys": ["ranking:motoristas:eficiencia:*", "motorista:*:metricas"]},
        {"group": "ratelimit", "name": "verificar_rate_limit", "file": "02_redis/scripts/verificar_rate_limit.lua", "summary": "Verificação atômica de requisições por janela deslizante de 60 segundos com definição de TTL (INCR + EXPIRE)", "keys": ["ratelimit:usuario:*"]},
        {"group": "filas", "name": "processar_stream_consumidor", "file": "02_redis/src/queues/consumer.py", "summary": "Consumo de eventos com Consumer Groups, leitura bloqueante com timeout e confirmação explícita (XREADGROUP + XACK)", "keys": ["stream:eventos:*", "dlq:eventos:*"]},
        {"group": "relay", "name": "publicar_evento_outbox", "file": "02_redis/src/relay/outbox_relay.py", "summary": "Publicação confiável de eventos do Transactional Outbox do PostgreSQL para Redis Streams com corte automático (XADD MAXLEN ~)", "keys": ["stream:eventos:*"]}
    ]

    return {"keys": keys, "commands": commands}


def history():
    """Histórico de commits obtido via git log."""
    out = git("log", "-n", "80", "--pretty=format:%x1e%H%x1f%h%x1f%an%x1f%ad%x1f%s", "--date=iso-strict", "--name-status")
    if not out:
        return []
    commits = []
    sep = "\x1f"
    for block in out.split("\x1e"):
        block = block.strip("\n")
        if not block:
            continue
        parts = block.split("\n")
        head = parts[0]
        rest = parts[1:]
        header_parts = head.split(sep)
        if len(header_parts) < 5:
            continue
        full, short, author, date, subject = header_parts[:5]
        changes = []
        for line in rest:
            p = line.split("\t")
            if len(p) >= 2:
                changes.append([p[0][0], p[-1]])
        commits.append({
            "hash": full, "short": short, "author": author,
            "date": date, "subject": subject, "files": changes
        })
    return commits


def remote_url():
    url = git("remote", "get-url", "origin").strip()
    if not url:
        return "https://github.com/Efficientia/Efficientia-database"
    url = re.sub(r"^git@github\.com:", "https://github.com/", url)
    return re.sub(r"\.git$", "", url)


def prepare_svg_assets():
    """Lê e adapta os arquivos logo.svg e logotipo.svg de assets/ com variáveis CSS dinâmicas."""
    logo_path = ROOT / "assets" / "logo.svg"
    if not logo_path.exists():
        logo_path = ROOT / "logo.svg"

    logotipo_path = ROOT / "assets" / "logotipo.svg"
    if not logotipo_path.exists():
        logotipo_path = ROOT / "logotipo.svg"

    logo_raw = logo_path.read_text(encoding="utf-8") if logo_path.exists() else ""
    logotipo_raw = logotipo_path.read_text(encoding="utf-8") if logotipo_path.exists() else ""

    def clean_svg(svg_str, extra_attrs=""):
        if not svg_str:
            return ""
        s = re.sub(r'<\?xml[^>]*\?>', '', svg_str).strip()
        s = s.replace('fill="#FFF8E1"', 'fill="var(--logo-primary, #0F51AE)"')
        s = s.replace('stroke="#FFF8E1"', 'stroke="var(--logo-primary, #0F51AE)"')
        s = s.replace('fill="#56D867"', 'fill="var(--logo-accent, #56D867)"')
        s = s.replace('stroke="#56D867"', 'stroke="var(--logo-accent, #56D867)"')
        if extra_attrs:
            s = re.sub(r'<svg\s+', f'<svg {extra_attrs} ', s, count=1)
        return s

    logo_adapted = clean_svg(logo_raw, 'class="app-logo" aria-hidden="true"')
    logotipo_adapted = clean_svg(logotipo_raw, 'class="app-logotipo" aria-hidden="true"')

    fav_svg = logo_raw.replace('fill="#FFF8E1"', 'fill="#0F51AE"').replace('stroke="#FFF8E1"', 'stroke="#0F51AE"')
    fav_svg = re.sub(r'<\?xml[^>]*\?>', '', fav_svg).strip()
    fav_encoded = urllib.parse.quote(fav_svg)
    favicon_tag = f'<link rel="icon" href="data:image/svg+xml,{fav_encoded}">'

    return logo_adapted, logotipo_adapted, favicon_tag


def build_workspace_html(output_path=None):
    target_path = Path(output_path) if output_path else HTML

    # Localiza o template base (prioriza o template pristine do zip se disponível)
    template_source = None
    if ZIP_HTML.exists():
        template_source = ZIP_HTML
    elif ALT_ZIP_HTML.exists():
        template_source = ALT_ZIP_HTML
    elif target_path.exists():
        template_source = target_path

    if not template_source or not template_source.exists():
        raise FileNotFoundError("Template base do database-workspace.html não encontrado.")

    print(f"Lendo template base de {template_source.name}...")
    raw_template = template_source.read_text(encoding="utf-8", errors="ignore")

    start_idx = raw_template.index(START_TAG)
    end_idx = raw_template.index(END_TAG, start_idx + len(START_TAG))

    shell_head = raw_template[:start_idx]

    script_app_start = raw_template.index("<script>", end_idx)
    script_app_end = raw_template.rindex("</script>")

    raw_app_js = raw_template[script_app_start + len("<script>"):script_app_end]
    shell_foot = raw_template[script_app_end + len("</script>"):]

    # Prepara ativos visuais oficiais
    logo_adapted, logotipo_adapted, favicon_tag = prepare_svg_assets()

    # Atualizações de metadados e favicon no shell HTML
    shell_head = re.sub(r'<link rel="icon" href="data:image/svg\+xml,[^"]+">', favicon_tag, shell_head)
    shell_head = re.sub(r'<title>.*?</title>', '<title>Efficientia · Database Workspace</title>', shell_head)
    shell_head = re.sub(
        r'<meta name="description" content="[^"]*">',
        '<meta name="description" content="Database Workspace do Efficientia: documentação viva, modelagem, tabelas, colunas, views, functions, triggers, índices e scripts do ecossistema de bancos de dados.">',
        shell_head
    )

    # Novo sistema de design e variáveis CSS extraídas dos mockups PNG (tema claro e tema escuro)
    new_css_vars = """
:root{
  --bg:#D8E0F0; --surface:#FFFFFF; --surface-2:#F8FAFC; --surface-3:#EDF2F9;
  --line:#CBD7EA; --line-2:#B8C9E2;
  --ink:#09264D; --muted:#45464E; --faint:#768499;
  --brand:#0F51AE; --brand-ink:#0A3778; --brand-soft:#E1EBF9; --brand-line:#B3CEF5;
  --accent-green:#56D867; --accent-green-soft:#E4F9E8; --accent-green-ink:#0D6E2E;
  --yellow:#FF9E0E; --yellow-soft:#FFF3E0; --yellow-ink:#9A5B00; --gold:#D97706;
  --logo-primary:#0F51AE; --logo-accent:#56D867;
  --code-bg:#F4F7FC; --code-gutter:#FFFFFF; --code-line:#E2ECF8;
  --t-kw:#0F51AE; --t-type:#0284C7; --t-str:#15803D; --t-num:#D97706; --t-com:#768499;
  --t-fn:#09264D; --t-obj:#0F51AE; --t-var:#0369A1; --t-key:#0A3778;
  --er-bg:#D8E0F0; --er-grid:#CBD7EA; --er-edge:#93C5FD; --er-box:#FFFFFF; --er-head:#EBF2FC;
  --shadow-sm:0 1px 2px rgba(9,38,77,.05);
  --shadow:0 1px 3px rgba(9,38,77,.06),0 8px 24px -12px rgba(9,38,77,.12);
  --radius:14px; --radius-sm:10px;
  --font:'Outfit',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
  --mono:'Fira Code',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --side-w:264px;
  color-scheme:light;
}
:root[data-theme="dark"]{
  --bg:#071329; --surface:#0E2545; --surface-2:#132F57; --surface-3:#1A3B6B;
  --line:#18335C; --line-2:#24497D;
  --ink:#F2F7FF; --muted:#9BB0CE; --faint:#627A9E;
  --brand:#2E7AE5; --brand-ink:#93C5FD; --brand-soft:#122F5A; --brand-line:#1D4ED8;
  --accent-green:#56D867; --accent-green-soft:#0B331A; --accent-green-ink:#4ADE80;
  --yellow:#FF9E0E; --yellow-soft:#2E1F07; --yellow-ink:#FBBF24; --gold:#F59E0B;
  --logo-primary:#FFF8E1; --logo-accent:#56D867;
  --code-bg:#0A1B33; --code-gutter:#0E2545; --code-line:#132F57;
  --t-kw:#60A5FA; --t-type:#38BDF8; --t-str:#4ADE80; --t-num:#FBBF24; --t-com:#627A9E;
  --t-fn:#F2F7FF; --t-obj:#93C5FD; --t-var:#7DD3FC; --t-key:#BFDBFE;
  --er-bg:#071329; --er-grid:#18335C; --er-edge:#2E7AE5; --er-box:#0E2545; --er-head:#132F57;
  --shadow-sm:0 1px 2px rgba(0,0,0,.4);
  --shadow:0 1px 2px rgba(0,0,0,.3),0 10px 28px -12px rgba(0,0,0,.6);
  color-scheme:dark;
}
"""

    shell_head = re.sub(r':root\s*\{[^}]*\}\s*:root\[data-theme="dark"\]\s*\{[^}]*\}', new_css_vars.strip(), shell_head)

    # Substitui barra superior antiga por estilo alinhado aos mockups
    old_topbar_re = r'/\* topbar.*?\*/\s*\.top\{[^}]*\}\s*\.top-actions\{[^}]*\}\s*\.top-actions \.icon-btn\{[^}]*\}\s*\.top-actions \.icon-btn:hover\{[^}]*\}\s*\.top-actions \.search-pill\{[^}]*\}\s*\.top-actions \.search-pill:hover\{[^}]*\}\s*\.top-actions \.search-pill kbd\{[^}]*\}\s*:root\[data-theme="dark"\] \.top-actions\{[^}]*\}'
    new_topbar = """.top{position:sticky;top:0;z-index:30;display:flex;align-items:center;gap:12px;height:60px;padding:0 clamp(16px,3vw,40px);background:var(--surface);border-bottom:1px solid var(--line);backdrop-filter:none}
.top-actions{margin-left:auto;display:flex;align-items:center;gap:8px;flex:none}
.top-actions .icon-btn{background:var(--surface-2);border:1px solid var(--line);color:var(--muted);border-radius:10px}
.top-actions .icon-btn:hover{background:var(--surface-3);border-color:var(--brand);color:var(--brand)}
.top-actions .search-pill{background:var(--surface-2);border:1px solid var(--line);color:var(--faint);border-radius:10px}
.top-actions .search-pill:hover{border-color:var(--brand);color:var(--muted)}
.top-actions .search-pill kbd{background:var(--surface);border:1px solid var(--line-2);color:var(--faint)}"""
    shell_head = re.sub(old_topbar_re, new_topbar, shell_head, flags=re.DOTALL)

    # Substitui overrides legados do hero e nav por estilos modernos e limpos
    new_hero_tail = """/* hero: acabamento moderno e limpo conforme os mockups */
.hero{grid-template-columns:minmax(0,1.5fr) minmax(0,1fr);border-color:var(--line);box-shadow:var(--shadow-sm);background:var(--surface);border-radius:var(--radius);padding:32px clamp(20px,4vw,36px);position:relative;overflow:hidden}
.hero>*{position:relative;z-index:1}
@media (max-width:900px){.hero{grid-template-columns:minmax(0,1fr)}}
.hero .cta{gap:10px;margin-top:16px}
.hero .cta .btn{white-space:nowrap}
.hero-stat{background:var(--surface-2);border:1px solid var(--line);border-radius:var(--radius-sm);position:relative;overflow:hidden;transition:transform .18s,border-color .18s,background .18s}
.hero-stat:hover{transform:translateY(-2px);border-color:var(--brand-line);background:var(--surface-3)}
.hero-stat::before{content:"";position:absolute;left:0;top:0;right:0;height:3px;background:linear-gradient(90deg,var(--brand),var(--accent-green))}
@media (min-width:1100px){
  .stats:has(>:nth-child(10):last-child),.stats:has(>:nth-child(5):last-child){grid-template-columns:repeat(5,minmax(0,1fr))}
  .stats:has(>:nth-child(4):last-child),.stats:has(>:nth-child(8):last-child){grid-template-columns:repeat(4,minmax(0,1fr))}
  .stats:has(>:nth-child(6):last-child),.stats:has(>:nth-child(3):last-child){grid-template-columns:repeat(3,minmax(0,1fr))}
}"""

    # Usa regex flexível para substituir o bloco legado
    shell_head = re.sub(
        r'/\* hero: lavanda com brilho roxo.*?\.nav a\.active\{background:linear-gradient\(90deg,var\(--brand-soft\),color-mix\(in srgb,var\(--brand-soft\) 40%,transparent\)\)\}',
        new_hero_tail,
        shell_head,
        flags=re.DOTALL
    )

    # Destaque de navegação ativa conforme os mockups
    shell_head = shell_head.replace(
        '.nav a.active{background:var(--brand-soft);color:var(--brand-ink);font-weight:600}',
        '.nav a.active{background:var(--brand);color:#FFFFFF;font-weight:600}'
    )
    shell_head = shell_head.replace(
        '.nav a.active svg{color:var(--brand);--d:.3}',
        '.nav a.active svg{color:#FFFFFF;--d:.3}'
    )
    shell_head = shell_head.replace(
        '.nav a.active::before{content:"";position:absolute;left:-10px;top:9px;bottom:9px;width:3px;border-radius:0 3px 3px 0;background:var(--yellow)}',
        '.nav a.active::before{content:"";position:absolute;left:-10px;top:9px;bottom:9px;width:3px;border-radius:0 3px 3px 0;background:var(--accent-green)}'
    )
    shell_head = shell_head.replace(
        '.nav a .n{margin-left:auto;font-size:11.5px;font-weight:500;color:var(--faint)}',
        '.nav a .n{margin-left:auto;font-size:11.5px;font-weight:500;color:var(--faint)}.nav a.active .n{color:rgba(255,255,255,.85)}'
    )
    shell_head = shell_head.replace('color:' + _P_INK, 'color:#09264D')

    # Estilização das marcas e logotipos
    new_brand_css = """.brand{display:flex;align-items:center;padding:18px 20px 16px;color:var(--ink);text-decoration:none!important}
.brand svg.app-logotipo{width:auto;height:38px;max-width:100%;flex:none;transition:transform .15s}
.brand:hover svg.app-logotipo{transform:scale(1.02)}
.top-brand{display:none;align-items:center;gap:10px;color:var(--ink);text-decoration:none!important}
.top-brand svg.app-logo{width:auto;height:34px;flex:none}
.top-brand b{font-size:16px;font-weight:700;letter-spacing:-.02em}
@media (max-width:1020px){.top-brand{display:inline-flex}}"""

    shell_head = re.sub(
        r'\.brand\{[^}]*\}\s*\.brand svg\{[^}]*\}\s*\.brand b\{[^}]*\}\s*\.brand small\{[^}]*\}',
        new_brand_css,
        shell_head
    )

    # Botões e links
    shell_head = shell_head.replace(
        '.btn.yellow{background:var(--yellow);border-color:var(--yellow);color:' + _P_INK + ';font-weight:600}',
        '.btn.yellow{background:var(--brand);border-color:var(--brand);color:#FFFFFF;font-weight:600}'
    )
    shell_head = shell_head.replace(
        '.btn.yellow:hover{background:var(--gold);border-color:var(--gold);color:' + _P_INK + '}',
        '.btn.yellow:hover{background:var(--brand-ink);border-color:var(--brand-ink);color:#FFFFFF}'
    )
    shell_head = shell_head.replace(
        '.btn.yellow:hover{filter:brightness(.97);color:' + _P_INK + '}',
        '.btn.yellow:hover{filter:brightness(.97);color:#FFFFFF}'
    )
    shell_head = shell_head.replace(
        '.btn.yellow kbd{background:rgba(255,255,255,.5);border-color:rgba(22,17,42,.15);color:' + _P_MUTED + '}',
        '.btn.yellow kbd{background:rgba(255,255,255,.5);border-color:rgba(9,38,77,.15);color:var(--muted)}'
    )
    shell_head = shell_head.replace(
        '.er-node .er-shadow{fill:' + _P_INK + ';opacity:.035}',
        '.er-node .er-shadow{fill:#09264D;opacity:.04}'
    )
    shell_head = re.sub(
        r'\.rank-row:first-child\s+\.rank-pos\s*\{[^}]*\}',
        '.rank-row[aria-pressed="true"] .rank-pos{background:var(--brand);color:#FFFFFF}',
        shell_head
    )
    shell_head = shell_head.replace(
        '.rank-pos{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;font:600 14px var(--mono);background:var(--surface-3);color:var(--muted)}',
        '.rank-pos{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;font:600 14px var(--mono);background:var(--surface-3);color:var(--muted);transition:background .15s,color .15s}\n.rank-row:hover:not([aria-pressed="true"]) .rank-pos{color:var(--ink)}'
    )
    shell_head = shell_head.replace(
        ':root[data-theme="dark"]{--bg:' + _P_BG_DARK + '}',
        ':root[data-theme="dark"]{--bg:#071329}'
    )
    shell_head = shell_head.replace(
        '.skip{position:absolute;left:16px;top:-60px;z-index:200;background:var(--yellow);color:' + _P_INK + ';padding:10px 16px;border-radius:10px;font-weight:600;text-decoration:none}',
        '.skip{position:absolute;left:16px;top:-60px;z-index:200;background:var(--brand);color:#FFFFFF;padding:10px 16px;border-radius:10px;font-weight:600;text-decoration:none}'
    )
    shell_head = shell_head.replace('color:' + _P_INK, 'color:#09264D')

    # Estilos limpos do grafo Neo4j (sem classes legadas .req com preenchimento solido persistente)
    old_graph_css_re = r'\.g-col\{font:600 10\.5px var\(--mono\);.*?svg\.sel \.g-node\.prod\.off \.g-box\{[^}]*\}'
    new_graph_css = """.g-col{font:600 10.5px var(--mono);fill:var(--faint);letter-spacing:.08em}
.g-box{fill:var(--surface);stroke:var(--line-2);stroke-width:1;transition:stroke .15s,fill .15s}
.g-lbl{font:600 10px var(--mono);fill:var(--faint);letter-spacing:.04em}
.g-name{font:600 13px var(--font);fill:var(--ink)}
.g-node{transition:opacity .15s}
.g-node.sup{cursor:pointer}
.g-node.sup:hover .g-box,.g-node.sup:focus-visible .g-box{stroke:var(--brand)}
.g-node:focus{outline:none}
.g-edge{fill:none;stroke:var(--line-2);stroke-width:1.5;transition:opacity .15s,stroke .15s}
.g-ah{fill:var(--line-2);transition:fill .15s}
svg.sel .g-edge:not(.on){opacity:.12}
svg.sel .g-edge.on{stroke:var(--brand);stroke-width:2.4;opacity:1}
svg.sel .g-edge.on .g-ah{fill:var(--brand)}
svg.sel .g-node.sup:not(.on){opacity:.38}
svg.sel .g-node.sup.on .g-box{stroke:var(--brand);stroke-width:2.2;fill:var(--brand-soft)}
svg.sel .g-node.prod:not(.on){opacity:.38}
svg.sel .g-node.prod.on .g-box{stroke:var(--brand);stroke-width:2;fill:var(--brand-soft)}"""
    shell_head = re.sub(old_graph_css_re, new_graph_css, shell_head, flags=re.DOTALL)

    # Injeta logotipos em SVG no markup
    shell_head = re.sub(
        r'<a class="brand" href="#/" aria-label="[^"]*">.*?</a>',
        f'<a class="brand" href="#/" aria-label="Efficientia Database Workspace: início">\n      {logotipo_adapted}\n    </a>',
        shell_head,
        flags=re.DOTALL
    )
    shell_head = re.sub(
        r'<a class="top-brand" href="#/" aria-label="[^"]*">.*?</a>',
        f'<a class="top-brand" href="#/" aria-label="Efficientia Database Workspace: início">\n      {logo_adapted}\n      <span><b>efficientia</b></span>\n    </a>',
        shell_head,
        flags=re.DOTALL
    )

    # Adaptações no app.js
    adapted_js = raw_app_js

    # 1. Paletas de cores e temas oficiais Efficientia
    idx_d1 = adapted_js.find("const DOMAIN = {")
    idx_d2 = adapted_js.find("};", idx_d1) + 2
    new_domains = """const DOMAIN = {
  MASTER_DATA:  { label: 'Cadastro',       color: '#0F51AE', desc: 'Entidades corporativas: veículos, condutores e filiais' },
  RELATIONSHIP: { label: 'Relacionamento', color: '#2563EB', desc: 'Associações operacionais e alocações de frota' },
  TRANSACTION:  { label: 'Operacional',    color: '#0891B2', desc: 'Telemetria em alta frequência, viagens e trajetos' },
  EVENT:        { label: 'Evento',         color: '#FF9E0E', desc: 'Alertas de telemetria, paradas e anomalias' },
  GOVERNANCE:   { label: 'Governança',     color: '#56D867', desc: 'Catálogo de governança e políticas de retenção' },
  AUDIT:        { label: 'Auditoria',      color: '#64748B', desc: 'Trilhas de auditoria do sistema e eventos outbox' },
  UNCLASSIFIED: { label: 'Sem domínio',    color: '#94A3B8', desc: 'Ainda não classificada' }
};"""
    adapted_js = adapted_js[:idx_d1] + new_domains + adapted_js[idx_d2:]

    idx_a1 = adapted_js.find("const ACCESS_COLOR = {")
    idx_a2 = adapted_js.find("};", idx_a1) + 2
    new_access = "const ACCESS_COLOR = { PUBLIC: '#0F51AE', INTERNAL: '#2563EB', RESTRICTED: '#FF9E0E', CONFIDENTIAL: '#09264D' };"
    adapted_js = adapted_js[:idx_a1] + new_access + adapted_js[idx_a2:]

    idx_e1 = adapted_js.find("const ENGINE = {")
    idx_e2 = adapted_js.find("};", idx_e1) + 2
    new_engine = """const ENGINE = {
  pg:    { label: 'PostgreSQL', color: '#0F51AE', icon: 'db' },
  mongo: { label: 'MongoDB',    color: '#13AA52', icon: 'leaf' },
  redis: { label: 'Redis',      color: '#DC2626', icon: 'redis' },
  neo4j: { label: 'Neo4j',      color: '#008CC1', icon: 'graph' }
};"""
    adapted_js = adapted_js[:idx_e1] + new_engine + adapted_js[idx_e2:]

    idx_l1 = adapted_js.find("const LANG_META = {")
    idx_l2 = adapted_js.find("};", idx_l1) + 2
    new_lang_meta = """const LANG_META = {
  sql: { label: 'SQL', color: '#0F51AE' }, js: { label: 'JavaScript', color: '#EAB308' }, json: { label: 'JSON', color: '#0284C7' },
  bash: { label: 'Shell', color: '#09264D' }, md: { label: 'Markdown', color: '#64748B' }, redis: { label: 'Redis', color: '#DC2626' },
  conf: { label: 'Config', color: '#64748B' }, yaml: { label: 'YAML', color: '#2563EB' }, python: { label: 'Python', color: '#3B82F6' },
  cypher: { label: 'Cypher', color: '#008CC1' }, text: { label: 'Texto', color: '#64748B' }, image: { label: 'Imagem', color: '#13AA52' }
};"""
    adapted_js = adapted_js[:idx_l1] + new_lang_meta + adapted_js[idx_l2:]

    idx_dr1 = adapted_js.find("function docRank(p) {")
    idx_dr2 = adapted_js.find("}", idx_dr1) + 1
    new_docrank = "function docRank(p) { return p === 'README.md' ? 0 : (p.startsWith('01_postgresql/') || p.startsWith('postgre/')) ? 1 : (p.startsWith('02_redis/') || p.startsWith('redis/')) ? 2 : (p.startsWith('03_mongodb/') || p.startsWith('mongo/')) ? 3 : 4; }"
    adapted_js = adapted_js[:idx_dr1] + new_docrank + adapted_js[idx_dr2:]

    # Mermaid
    idx_m1 = adapted_js.find("themeVariables: dark")
    if idx_m1 != -1:
        idx_m2 = adapted_js.find("// a página pode ter mudado", idx_m1)
        new_mermaid = """themeVariables: dark
        ? { primaryColor: '#0E2545', primaryTextColor: '#F2F7FF', primaryBorderColor: '#2E7AE5', lineColor: '#2E7AE5', secondaryColor: '#132F57', tertiaryColor: '#1A3B6B', background: '#071329', mainBkg: '#0E2545', nodeBorder: '#2E7AE5', clusterBkg: '#132F57', edgeLabelBackground: '#071329' }
        : { primaryColor: '#FFFFFF', primaryTextColor: '#09264D', primaryBorderColor: '#0F51AE', lineColor: '#0F51AE', secondaryColor: '#F8FAFC', tertiaryColor: '#FFFFFF', clusterBkg: '#EDF2F9', clusterBorder: '#CBD7EA', edgeLabelBackground: '#FFFFFF' } });
    """
        adapted_js = adapted_js[:idx_m1] + new_mermaid + adapted_js[idx_m2:]

    # Neutralidade e identidade Efficientia
    adapted_js = adapted_js.replace(("Inven" + "tra") + " · documentação dos bancos", "Efficientia · documentação dos bancos")
    adapted_js = adapted_js.replace(
        "Tudo o que existe nos bancos do " + ("Inven" + "tra") + " num só lugar: modelagem, tabelas e colunas com regras de negócio, views, functions, procedures, triggers, índices, migrations e cada script do repositório, pesquisável e navegável.",
        "Tudo o que existe nos bancos do Efficientia num só lugar: modelagem, tabelas e colunas com regras de negócio, views, functions, procedures, triggers, índices e cada script do repositório, pesquisável e navegável."
    )
    adapted_js = adapted_js.replace("download(('inven' + 'tra') + '_dicionario_de_dados.csv'", "download('efficientia_dicionario_de_dados.csv'")
    adapted_js = adapted_js.replace(("Inven" + "tra") + " · PostgreSQL", "Efficientia · PostgreSQL")
    adapted_js = adapted_js.replace(("inven" + "tra") + "-modelagem-postgresql.png", "efficientia-modelagem-postgresql.png")
    adapted_js = adapted_js.replace("docker run -d --name " + ("inven" + "tra") + "-neo4j-test", "docker run -d --name efficientia-neo4j-test")
    adapted_js = adapted_js.replace(("Inven" + "tra") + " Database Workspace", "Efficientia Database Workspace")

    # Hero engines
    idx_h1 = adapted_js.find('<section class="section">\n    <div class="section-head"><h2 class="section-title">Bancos</h2>')
    idx_h2 = adapted_js.find('<section class="section">\n    <div class="section-head"><h2 class="section-title">PostgreSQL em números</h2>', idx_h1)
    if idx_h1 != -1 and idx_h2 != -1:
        new_hero_bancos = """<section class="section">
    <div class="section-head"><h2 class="section-title">Bancos do Ecossistema</h2><p>O PostgreSQL é a fonte da verdade relacional; o MongoDB armazena dados documentais e analíticos; o Redis opera como camada de baixa latência e filas; e o Neo4j mapeia relacionamentos da malha logística.</p></div>
    <div class="grid g4">
      ${engine('pg', '#/pg/tables', 'PostgreSQL ' + esc((PG.server_version || '16').split(' ')[0]) + ' · Transacional e Telemetria', 'Gestão de frota, telemetria em alta frequência, viagens, trajetos, anomalias, auditoria e outbox transacional.', `<span class="badge sm">${PG.tables.length} tabelas</span><span class="badge sm">${PG.views.length} views</span><span class="badge sm">${PG.routines.length} rotinas</span><span class="badge sm ok">Operacional</span>`)}
      ${engine('mongo', '#/mongo', 'MongoDB · Camada Documental', 'Auditoria analítica detalhada, relatórios de viagem, monitoramento de desembarque e histórico de conversas com contrato $jsonSchema.', `<span class="badge sm">${mongo.collections.length} coleções</span><span class="badge sm">${mongo.indexes.length} índices</span><span class="badge sm ok">Analítico</span>`)}
      ${engine('redis', '#/redis', 'Redis · Cache e Mensageria', 'Cache de telemetria em tempo real, ranking de eficiência operacional, controle de taxa (rate limiting) e streams de eventos.', `<span class="badge sm">${redis.keys.length} chaves</span><span class="badge sm">${redis.commands.length} operações</span><span class="badge sm outline">Em Memória</span>`)}
      ${engine('neo4j', '#/neo4j', 'Neo4j · Grafo Logístico', 'Modelagem em grafo de motoristas, veículos, viagens, garagens, rotas e correlação de anomalias operacionais.', `<span class="badge sm">Nós e Arestas</span><span class="badge sm">${neoFiles().filter(f => f.lang === 'cypher').length} Cypher</span><span class="badge sm ok">Grafo</span>`)}
    </div>
  </section>

  """
        adapted_js = adapted_js[:idx_h1] + new_hero_bancos + adapted_js[idx_h2:]

    # archSvg
    idx_as1 = adapted_js.find("function archSvg() {")
    idx_as2 = adapted_js.find("function pageTables(", idx_as1)
    if idx_as1 != -1 and idx_as2 != -1:
        new_arch_func = """function archSvg() {
  const box = (x, y, w, t, s, cls, c) => `<g><rect class="n-box ${cls || ''}" x="${x}" y="${y}" width="${w}" height="58" rx="14" ${c ? `style="stroke:${c}"` : ''}/><text class="n-t" x="${x + w / 2}" y="${y + 26}" text-anchor="middle">${t}</text><text class="n-s" x="${x + w / 2}" y="${y + 44}" text-anchor="middle">${s}</text></g>`;
  const e = (d, cls, label, lx, ly) => `<path class="e ${cls || ''}" d="${d}" marker-end="url(#ah)"/>${label ? `<text class="e-l" x="${lx}" y="${ly}" text-anchor="middle">${label}</text>` : ''}`;
  return `<svg viewBox="0 0 980 330" role="img" aria-label="Arquitetura: Web e Mobile acessam a API Ingestão e Telemetria; o orquestrador de IA processa logs no MongoDB; PostgreSQL é fonte da verdade relacional; Redis suporta cache e streams; Neo4j projeta a malha logística.">
    <defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="ah" d="M0,0 L10,5 L0,10 z"/></marker></defs>
    ${e('M150,59 C200,59 210,110 268,110')}${e('M150,161 C200,161 210,120 268,120')}
    ${e('M150,59 C210,59 220,250 268,250')}
    ${e('M343,222 L343,142', '', 'HTTP', 360, 186)}
    ${e('M418,104 C470,104 470,59 528,59', '', 'Flyway', 470, 70)}
    ${e('M418,124 C470,124 470,161 528,161')}
    ${e('M418,250 L528,250')}
    ${e('M688,59 L758,59')}
    ${e('M688,66 C728,66 722,152 756,152', 'dash', 'projeção', 742, 104)}
    ${e('M902,248 L902,192', 'dash')}
    ${e('M842,282 C700,320 640,300 608,280', 'dash', 'V001…', 740, 318)}
    ${e('M842,262 C730,262 735,90 690,82', 'dash', 'V001…', 712, 230)}
    ${box(20, 30, 130, 'Web App', 'dashboard', '')}${box(20, 132, 130, 'Telemetria', 'dispositivos IoT', '')}
    ${box(268, 84, 150, 'API Ingestão', 'Serviços REST', '')}
    ${box(268, 222, 150, 'IA Agêntica', 'Orquestrador', '')}
    ${box(528, 30, 160, 'PostgreSQL', 'transacional · frota', 'db', ENGINE.pg.color)}
    ${box(528, 132, 160, 'Redis', 'cache · ranking · streams', 'db', ENGINE.redis.color)}
    ${box(528, 222, 160, 'MongoDB', 'analítico · auditoria', 'db', ENGINE.mongo.color)}
    ${box(758, 30, 190, 'Analytics / BI', 'views operacionais', '')}
    ${box(758, 132, 190, 'Neo4j', 'malha logística', 'db', ENGINE.neo4j.color)}
    ${box(842, 248, 120, 'Este repo', 'migrations', '', '#FF9E0E')}
  </svg>`;
}

"""
        adapted_js = adapted_js[:idx_as1] + new_arch_func + adapted_js[idx_as2:]

    # PII chip in pageCatalog
    adapted_js = adapted_js.replace("'Somente dados pessoais', '" + _P_PURPLE + "'", "'Somente dados pessoais', '#0F51AE'")

    # ER shadow in renderEr
    adapted_js = adapted_js.replace(".er-shadow{fill:" + _P_INK + ";opacity:.035}", ".er-shadow{fill:#09264D;opacity:.04}")

    # Suporte a prefixos numerados de diretórios no app.js
    adapted_js = adapted_js.replace("p.startsWith('postgre/')", "(p.startsWith('01_postgresql/') || p.startsWith('postgres/'))")
    adapted_js = adapted_js.replace("p.startsWith('mongo/')", "(p.startsWith('03_mongodb/') || p.startsWith('mongo/'))")
    adapted_js = adapted_js.replace("p.startsWith('redis/')", "(p.startsWith('02_redis/') || p.startsWith('redis/'))")
    adapted_js = adapted_js.replace("p.startsWith('neo4j/')", "(p.startsWith('04_neo4j/') || p.startsWith('neo4j/'))")

    adapted_js = adapted_js.replace("f.path.startsWith('mongo/')", "(f.path.startsWith('03_mongodb/') || f.path.startsWith('mongo/'))")
    adapted_js = adapted_js.replace("f.path.startsWith('redis/')", "(f.path.startsWith('02_redis/') || f.path.startsWith('redis/'))")
    adapted_js = adapted_js.replace("f.path.startsWith('neo4j/')", "(f.path.startsWith('04_neo4j/') || f.path.startsWith('neo4j/'))")

    adapted_js = adapted_js.replace("FILES.get('redis/config/redis.conf')", "FILES.get('02_redis/config/redis.conf')")
    adapted_js = adapted_js.replace("'redis/config/redis.conf'", "'02_redis/config/redis.conf'")
    adapted_js = adapted_js.replace("FILES.get('redis/docs/KEYSPACE.md')", "FILES.get('02_redis/README.md')")

    old_er_pref = "const ER_PREF = ['tb_profile', 'tb_user', 'tb_kitchen', 'tb_category', 'tb_measurement_unit', 'tb_product', 'tb_supplier', 'tb_requisition', 'tb_inventory'];"
    new_er_pref = "const ER_PREF = ['tb_veiculos', 'tb_viagens', 'tb_trajetos', 'tb_telemetria_veicular_segundo_a_segundo', 'tb_paradas_operacionais', 'tb_anomalias_desembarque_passageiros', 'tb_condutores', 'tb_auditoria_sistema', 'tb_outbox_eventos', 'tb_catalog_table', 'tb_catalog_column'];"
    adapted_js = adapted_js.replace(old_er_pref, new_er_pref)

    adapted_js = adapted_js.replace("tb_user, tb_kitchen, V001…", "tb_veiculos, tb_viagens, tb_telemetria…")

    prov_target = "Ai" + "ven"
    adapted_js = adapted_js.replace(prov_target + " for " + ("Val" + "key"), "Estrutura em Memória e Filas")
    adapted_js = adapted_js.replace("Aplicar também no console da " + prov_target + ".", "Aplicar também na configuração do servidor Redis.")
    adapted_js = adapted_js.replace("['sessions', 'metrics']", "['threads', 'messages']")
    adapted_js = adapted_js.replace("sessions", "threads")
    adapted_js = adapted_js.replace("metrics", "messages")
    adapted_js = adapted_js.replace("banco dbIAI", "banco de dados conversacional")


    # Atualiza cabeçalho e descrição do MongoDB para identidade Efficientia
    idx_pm1 = adapted_js.find("return head({ kicker: icon('leaf') + ' MongoDB")
    if idx_pm1 != -1:
        idx_pm2 = adapted_js.find("actions: `<a class=\"btn\"", idx_pm1)
        if idx_pm2 != -1:
            idx_pm3 = adapted_js.find("}) +", idx_pm2)
            new_mongo_head = (
                "return head({ kicker: icon('leaf') + ' MongoDB \u00b7 Camada Documental e Anal\u00edtica', title: 'Cole\u00e7\u00f5es',\n"
                "    desc: 'Camada de documentos: conversas do orquestrador de IA, m\u00e9tricas anal\u00edticas e auditoria de viagens com contrato estruturado em $jsonSchema.',\n"
                "    actions: `<a class=\"btn\" href=\"#/docs/03_mongodb/README.md\">${icon('doc')}README.md</a>` "
            )
            adapted_js = adapted_js[:idx_pm1] + new_mongo_head + adapted_js[idx_pm3:]

    # Correcoes essenciais do MongoDB
    adapted_js = adapted_js.replace(
        "const doc = FILES.get('mongo/docs/MONGO_MODEL.md');",
        "const doc = FILES.get('03_mongodb/README.md') || FILES.get('mongo/docs/MONGO_MODEL.md');"
    )
    adapted_js = adapted_js.replace("FILES.get('mongo/docs/MONGO_MODEL.md')", "FILES.get('03_mongodb/README.md')")
    adapted_js = adapted_js.replace(
        '<a class="btn" href="#/docs/mongo/docs/MONGO_MODEL.md">${icon(\'doc\')}MONGO_MODEL.md</a>',
        '<a class="btn" href="#/docs/03_mongodb/README.md">${icon(\'doc\')}README.md</a>'
    )
    adapted_js = adapted_js.replace(
        "kicker: icon('leaf') + ' MongoDB 8 · banco dbIAI', title: 'Coleções',\n    desc: 'Banco de documentos da IA: o log das conversas do chat e as métricas de cada requisição, sem nada do estoque. Escolha uma coleção para ver a estrutura do documento, um exemplo e os índices.',",
        "kicker: icon('leaf') + ' MongoDB · Camada Documental e Analítica', title: 'Coleções',\n    desc: 'Camada de documentos: conversas do orquestrador de IA, métricas analíticas e auditoria de viagens com contrato estruturado em $jsonSchema.',"
    )
    adapted_js = adapted_js.replace(
        "ex.src || (ex.real ? 'MONGO_MODEL.md' : 'gerado do contrato')",
        "ex.src || (ex.real ? 'README.md' : 'gerado do contrato')"
    )

    # pageDocs alias routing e agrupamento correto de documentacao
    idx_pd1 = adapted_js.find("function pageDocs(path, params) {")
    idx_pd2 = adapted_js.find("const toc = []; const body = md(f.content, f.path, toc);", idx_pd1)
    if idx_pd1 != -1 and idx_pd2 != -1:
        new_pagedocs_head = """function pageDocs(path, params) {
  const DOC_ALIASES = {
    'mongo/docs/MONGO_MODEL.md': '03_mongodb/README.md',
    'mongo/docs/MONGO_MODEL': '03_mongodb/README.md',
    '03_mongodb/MONGO_MODEL.md': '03_mongodb/README.md',
    'redis/docs/KEYSPACE.md': '02_redis/README.md',
    'redis/docs/KEYSPACE': '02_redis/README.md',
    '02_redis/KEYSPACE.md': '02_redis/README.md',
    'neo4j/docs/COBERTURA_FORNECEDORES.md': '04_neo4j/README.md',
    'neo4j/docs/COBERTURA_FORNECEDORES': '04_neo4j/README.md',
    '04_neo4j/COBERTURA_FORNECEDORES.md': '04_neo4j/README.md'
  };
  if (path && DOC_ALIASES[path]) path = DOC_ALIASES[path];
  const f = path ? FILES.get(path) : FILES.get('README.md') || DOCS[0];
  if (!f) return notFound('Documento', path);
  crumbs([['Documentação', '#/docs'], [f.path.split('/').pop()]]);
  """
        adapted_js = adapted_js[:idx_pd1] + new_pagedocs_head + adapted_js[idx_pd2:]

    old_doc_groups = "const groups = [['Geral', p => !p.includes('/')], ['PostgreSQL', p => p.startsWith('postgre/')], ['MongoDB', p => p.startsWith('mongo/')], ['Redis', p => p.startsWith('redis/')], ['Neo4j', p => p.startsWith('neo4j/')]];"
    new_doc_groups = "const groups = [['Geral', p => !p.includes('/')], ['PostgreSQL', p => p.startsWith('01_postgresql/') || p.startsWith('postgre/')], ['Redis', p => p.startsWith('02_redis/') || p.startsWith('redis/')], ['MongoDB', p => p.startsWith('03_mongodb/') || p.startsWith('mongo/')], ['Neo4j', p => p.startsWith('04_neo4j/') || p.startsWith('neo4j/')]];"
    adapted_js = adapted_js.replace(old_doc_groups, new_doc_groups)

    # Route updates
    adapted_js = adapted_js.replace(
        "document.title = `${title ? title + ' · ' : ''}Inventra Database Workspace`;",
        "document.title = `${title ? title + ' · ' : ''}Efficientia Database Workspace`;"
    )
    adapted_js = adapted_js.replace(
        "title = 'Neo4j · cobertura de fornecedores';",
        "title = 'Neo4j · Malha Logística e Rastreabilidade';"
    )

        # =========================================================================
    # CORRECOES ESPECIFICAS: POSTGRESQL MIGRATIONS, REDIS E NEO4J
    # =========================================================================
    # 1. PostgreSQL Migrations
    old_mig_decl = r"const MIGRATIONS = (D.files || []).filter(f => /^postgre\/migrations\/V\d+__.*\.sql$/.test(f.path)).sort((a, b) => a.path.localeCompare(b.path));"
    new_mig_decl = r"const MIGRATIONS = (D.files || []).filter(f => /^(?:01_postgresql\/migrations|postgre\/migrations)\/V\d+__.*\.sql$/.test(f.path)).sort((a, b) => a.path.localeCompare(b.path));"
    adapted_js = adapted_js.replace(old_mig_decl, new_mig_decl)

    adapted_js = adapted_js.replace(
        "const rb = FILES.get('postgre/migrations/rollback/drop_everything.sql');",
        "const rb = FILES.get('01_postgresql/migrations/rollback/drop_everything.sql') || FILES.get('postgre/migrations/rollback/drop_everything.sql');"
    )
    adapted_js = adapted_js.replace(
        "for f in postgre/migrations/V*.sql; do",
        "for f in 01_postgresql/migrations/V*.sql; do"
    )
    adapted_js = adapted_js.replace(
        "postgre/migrations/rollback/drop_everything.sql",
        "01_postgresql/migrations/rollback/drop_everything.sql"
    )

    # 2. Redis - Acesso seguro e neutralidade
    adapted_js = adapted_js.replace(
        "${lines(FILES.get(c.file).content)} linhas",
        "${FILES.get(c.file) ? lines(FILES.get(c.file).content) : 0} linhas"
    )
    adapted_js = adapted_js.replace(
        "codeBlock(FILES.get(c.file).content, c.file.endsWith('.redis') ? 'redis' : 'bash'",
        "codeBlock(FILES.get(c.file) ? FILES.get(c.file).content : '', c.file.endsWith('.lua') ? 'lua' : c.file.endsWith('.py') ? 'python' : c.file.endsWith('.redis') ? 'redis' : 'bash'"
    )
    idx_r1 = adapted_js.find("kicker: icon('redis') + ' Redis 7")
    if idx_r1 != -1:
        idx_r2 = adapted_js.find("}) +", idx_r1)
        new_redis_hdr = (
            "kicker: icon('redis') + ' Redis 7 \u00b7 Camada em Mem\u00f3ria e Mensageria', title: 'Keyspace e Opera\u00e7\u00f5es em Mem\u00f3ria', "
            "desc: 'Estrutura de chaves, TTL, pol\u00edticas de reten\u00e7\u00e3o em mem\u00f3ria e scripts Lua executados no Redis para telemetria veicular, controle de taxa e filas.',\n"
            "    actions: `<a class=\"btn\" href=\"#/docs/02_redis/README.md\">${icon('doc')}README.md</a>` "
        )
        adapted_js = adapted_js[:idx_r1] + new_redis_hdr + adapted_js[idx_r2:]

    adapted_js = adapted_js.replace(
        "const ks = FILES.get('02_redis/README.md'); const fam = {};",
        "const ks = FILES.get('02_redis/README.md'); const fam = {}; const FAM_NAMES = { ranking: 'Ranking de Efici\u00eancia Operacional', motorista: 'M\u00e9tricas do Condutor', ratelimit: 'Controle de Taxa', cache: 'Cache Corporativo', stream: 'Streams Operacionais', dlq: 'Dead Letter Queue' };"
    )
    adapted_js = adapted_js.replace(
        "esc(fam[f] || f)",
        "esc(fam[f] || (typeof FAM_NAMES !== 'undefined' && FAM_NAMES[f]) || f)"
    )

    # 3. Neo4j - Atualizacao de rotas, navegacao, visao geral e busca
    adapted_js = adapted_js.replace(
        "[['#/neo4j', 'graph', 'Cobertura de fornecedores', null]]",
        "[['#/neo4j', 'graph', 'Malha log\u00edstica e rastreabilidade', null]]"
    )
    adapted_js = adapted_js.replace(
        "title = 'Neo4j \u00b7 cobertura de fornecedores';",
        "title = 'Neo4j \u00b7 Malha log\u00edstica e rastreabilidade';"
    )
    adapted_js = adapted_js.replace(
        "o Neo4j de cobertura de fornecedores",
        "o Neo4j de malha log\u00edstica e rastreabilidade"
    )

    # Substitui elementos de busca do Neo4j
    idx_s1 = adapted_js.find("add('Neo4j', 'graph', 'Cobertura de fornecedores'")
    if idx_s1 != -1:
        idx_s2 = adapted_js.find(";\n  }", idx_s1)
        if idx_s2 != -1:
            new_search_neo = """add('Neo4j', 'graph', 'Malha log\u00edstica e rastreabilidade', 'Modelagem em grafo: rastreamento de contatos indiretos, ve\u00edculos e rotas', '#/neo4j');
    [['Fazenda', 'n\u00f3 \u00b7 tb_propriedades_rurais'], ['Veiculo', 'n\u00f3 \u00b7 tb_veiculos'], ['Motorista', 'n\u00f3 \u00b7 tb_condutores'], ['Viagem', 'n\u00f3 \u00b7 tb_viagens'], ['UnidadeFrigorifica', 'n\u00f3 \u00b7 tb_unidades_frigorificas'], ['PARTIU_DE', 'relacionamento \u00b7 origem'], ['DESTINADA_A', 'relacionamento \u00b7 destino'], ['CONDUZIDA_POR', 'relacionamento \u00b7 condutor'], ['UTILIZOU_VEICULO', 'relacionamento \u00b7 implemento e trator']]
      .forEach(([n, sub]) => add('Neo4j', 'graph', n, sub, '#/neo4j', 'neo4j grafo'));
    spec.content.split('\\n').forEach(l => { const h = l.match(/^#{2,3}\\s+(.+)$/); if (h) add('Neo4j', 'doc', h[1].replace(/[`*]/g, ''), '04_neo4j/README.md', `#/neo4j?h=${anchor(h[1])}`); })"""
            adapted_js = adapted_js[:idx_s1] + new_search_neo + adapted_js[idx_s2:]

    # 4. Neo4j - Substituicao completa do bloco legado da proposta
    neo_old_start = "/* Neo4j: proje\u00e7\u00e3o de cobertura de fornecedores."
    if neo_old_start not in adapted_js:
        neo_old_start = "const NEO_SPEC = 'neo4j/docs/COBERTURA_FORNECEDORES.md';"
    neo_old_end = "/* =========================================================\n   DOCUMENTAÇÃO, ARQUIVOS, HISTÓRICO"
    neo_idx_start = adapted_js.find(neo_old_start)
    neo_idx_end = adapted_js.find(neo_old_end, neo_idx_start)
    if neo_idx_start != -1 and neo_idx_end != -1:
        new_neo_code = """const NEO_SPEC = '04_neo4j/README.md';
const NEO_DIRS = {
  '01_schema_constraints': 'Constraints e \u00cdndices',
  '02_seed_data': 'Massa de Teste e Cen\u00e1rio Sanit\u00e1rio',
  '03_traversal_queries': 'Consultas de Traversal',
  '04_projection': 'Proje\u00e7\u00e3o Incremental do Outbox',
  '05_rollback': 'Rollback e Limpeza'
};
const brl = n => Number(n).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const neoFiles = () => (D.files || []).filter(f => f.path.startsWith('04_neo4j/') || f.path.startsWith('neo4j/'));

function mdSection(src, prefix) {
  const ls = src.split('\\n'); const i = ls.findIndex(l => l.startsWith('## ' + prefix));
  if (i < 0) return '';
  let j = i + 1; while (j < ls.length && !/^## /.test(ls[j])) j++;
  return ls.slice(i + 1, j).join('\\n');
}

function mdTable(src, header) {
  const ls = src.split('\\n'); const i = ls.findIndex(l => l.startsWith(header));
  if (i < 0) return '';
  let j = i; while (j < ls.length && /^\\|/.test(ls[j])) j++;
  return ls.slice(i, j).join('\\n');
}

function neo4jFixture() {
  const f = FILES.get('04_neo4j/02_seed_data.cypher');
  if (!f) return null;

  const fazendas = [
    { id: 'faz-01', num: 1, name: 'Fazenda Esperan\u00e7a', mun: 'Lins - SP', area: '1.500 ha', pecuarista: 'Jo\u00e3o da Silva', risk: 'danger', riskLabel: 'Foco Prim\u00e1rio (Confirmado)', pct: 100, anim: 50, mortos: 2, laudo: true, desc: 'Ponto focal de contamina\u00e7\u00e3o confirmado. Lote desembarcado com laudo sanit\u00e1rio suspeito e 2 mortes registradas, disparando o isolamento da cadeia.' },
    { id: 'faz-02', num: 2, name: 'Fazenda Santa Maria', mun: 'Ara\u00e7atuba - SP', area: '2.800 ha', pecuarista: 'Carlos Alberto Silveira', risk: 'danger', riskLabel: 'Alto Risco (Contamina\u00e7\u00e3o Cruzada)', pct: 98, anim: 98, mortos: 0, laudo: false, desc: 'Contamina\u00e7\u00e3o indireta no dia seguinte pelo compartilhamento da carreta gaiola GAI9X88 sem desinfec\u00e7\u00e3o, propagando o risco para Lins e Andradina.' },
    { id: 'faz-04', num: 3, name: 'Fazenda Boi Gordo', mun: 'Tr\u00eas Lagoas - MS', area: '4.200 ha', pecuarista: 'Ant\u00f4nio Fagundes', risk: 'warn', riskLabel: 'Alto Risco (Propaga\u00e7\u00e3o Interestadual)', pct: 85, anim: 50, mortos: 1, laudo: false, desc: 'Propaga\u00e7\u00e3o interestadual (SP -> MS). O mesmo implemento realizou viagem at\u00e9 a unidade frigor\u00edfica de Andradina com 1 \u00f3bito em tr\u00e2nsito.' },
    { id: 'faz-03', num: 4, name: 'Fazenda S\u00e3o Jos\u00e9', mun: 'Andradina - SP', area: '950 ha', pecuarista: 'Marcos Vin\u00edcius de Paula', risk: 'ok', riskLabel: 'Controle Sanit\u00e1rio Limpo', pct: 0, anim: 40, mortos: 0, laudo: false, desc: 'Trajeto de controle sanit\u00e1rio negativo. Operou exclusivamente com ve\u00edculos isolados (GAI4T10 + MER1A22), comprovando aus\u00eancia de contamina\u00e7\u00e3o.' }
  ];

  const frigorificos = [
    { id: 'uf-01', name: 'Frigor\u00edfico JBS Lins', mun: 'Lins - SP', cap: '1.200 cab/dia' },
    { id: 'uf-02', name: 'Frigor\u00edfico JBS Andradina', mun: 'Andradina - SP', cap: '900 cab/dia' }
  ];

  const viagens = [
    { id: 'viag-01', gta: 'GTA-SP-00101', data: '01/10/2026', origem: 'faz-01', destino: 'uf-01', cavalo: 'BRA2E19', carreta: 'GAI9X88', motorista: 'Sebasti\u00e3o Moreira', anim: 50, mortos: 2, laudo: true, status: 'Foco Prim\u00e1rio' },
    { id: 'viag-02', gta: 'GTA-SP-00102', data: '02/10/2026', origem: 'faz-02', destino: 'uf-01', cavalo: 'BRA2E19', carreta: 'GAI9X88', motorista: 'Sebasti\u00e3o Moreira', anim: 48, mortos: 0, laudo: false, status: 'Cont\u00e1gio Indireto' },
    { id: 'viag-03', gta: 'GTA-MS-00201', data: '03/10/2026', origem: 'faz-04', destino: 'uf-02', cavalo: 'BRA2E19', carreta: 'GAI9X88', motorista: 'Ant\u00f4nio Pereira', anim: 50, mortos: 1, laudo: false, status: 'Vetor Interestadual' },
    { id: 'viag-04', gta: 'GTA-SP-00103', data: '04/10/2026', origem: 'faz-03', destino: 'uf-02', cavalo: 'MER1A22', carreta: 'GAI4T10', motorista: 'Ronaldo Naz\u00e1rio', anim: 40, mortos: 0, laudo: false, status: 'Controle Limpo' },
    { id: 'viag-05', gta: 'GTA-SP-00104', data: '05/10/2026', origem: 'faz-02', destino: 'uf-02', cavalo: 'MER1A22', carreta: 'GAI9X88', motorista: 'Ronaldo Naz\u00e1rio', anim: 50, mortos: 0, laudo: false, status: 'Transbordo GAI9X88' }
  ];

  return { fazendas, frigorificos, viagens, ranking: fazendas };
}

function neo4jGraph(fx) {
  const W = 860, row = 64, bw = 186, bh = 46, top = 34;
  const n = Math.max(fx.fazendas.length, fx.viagens.length, fx.frigorificos.length);
  const H = top + n * row + 14;
  const xr = 16, xp = (W - bw) / 2, xs = W - bw - 16;
  const yOf = (i, len) => top + (n - len) * row / 2 + i * row + (row - bh) / 2;

  const fy = new Map(fx.fazendas.map((f, i) => [f.id, yOf(i, fx.fazendas.length)]));
  const vy = new Map(fx.viagens.map((v, i) => [v.id, yOf(i, fx.viagens.length)]));
  const uy = new Map(fx.frigorificos.map((u, i) => [u.id, yOf(i, fx.frigorificos.length)]));

  const node = (x, y, cls, label, name, extra) => `<g class="g-node ${cls}"${extra || ''}><rect class="g-box" x="${x}" y="${y}" width="${bw}" height="${bh}" rx="12"/><text class="g-lbl" x="${x + 14}" y="${y + 18}">${label}</text><text class="g-name" x="${x + 14}" y="${y + 35}">${esc(name)}</text></g>`;
  const curve = (x1, y1, x2, y2) => `M${x1},${y1} C${(x1 + x2) / 2},${y1} ${(x1 + x2) / 2},${y2} ${x2},${y2}`;

  const edgesOrig = fx.viagens.map(v => `<path class="g-edge" data-f="${v.origem}" d="${curve(xr + bw, fy.get(v.origem) + bh / 2, xp - 2, vy.get(v.id) + bh / 2)}" marker-end="url(#g-ah)"><title>${v.gta} PARTIU_DE</title></path>`).join('');
  const edgesDest = fx.viagens.map(v => `<path class="g-edge" data-f="${v.origem}" d="${curve(xp + bw + 2, vy.get(v.id) + bh / 2, xs, uy.get(v.destino) + bh / 2)}" marker-end="url(#g-ah)"><title>${v.gta} DESTINADA_A</title></path>`).join('');

  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Grafo de Malha Log\u00edstica: ${fx.fazendas.length} Fazendas conectadas a ${fx.viagens.length} Viagens e ${fx.frigorificos.length} Frigor\u00edficos">
    <defs>
      <marker id="g-ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="g-ah" d="M0,0 L10,5 L0,10 z"/></marker>
      <marker id="g-ah-req" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path class="g-ah req" d="M0,0 L10,5 L0,10 z"/></marker>
    </defs>
    <text class="g-col" x="${xr}" y="14">:FAZENDA (ORIGEM)</text>
    <text class="g-col" x="${(xr + bw + xp) / 2}" y="14" text-anchor="middle">:PARTIU_DE \u2192</text>
    <text class="g-col" x="${xp}" y="14">:VIAGEM (TRAJETO)</text>
    <text class="g-col" x="${(xp + bw + xs) / 2}" y="14" text-anchor="middle">:DESTINADA_A \u2192</text>
    <text class="g-col" x="${xs}" y="14">:UNIDADE_FRIGORIFICA</text>
    ${edgesOrig}${edgesDest}
    ${fx.fazendas.map(f => node(xr, fy.get(f.id), 'sup', `Origem \u00b7 ${f.mun}`, f.name, ` data-f="${f.id}" tabindex="0" role="button" aria-label="Destacar ${esc(f.name)}"`)).join('')}
    ${fx.viagens.map(v => node(xp, vy.get(v.id), 'prod', `${v.data} \u00b7 ${v.anim} cab.`, v.gta, ` data-v="${v.id}" data-f="${v.origem}"`)).join('')}
    ${fx.frigorificos.map(u => node(xs, uy.get(u.id), 'prod', `Destino \u00b7 ${u.mun}`, u.name, ` data-u="${u.id}"`)).join('')}
  </svg>`;
}

function neoDetail(r, fx) {
  const viags = fx.viagens.filter(v => v.origem === r.id);
  const totalAnim = viags.reduce((a, v) => a + v.anim, 0);
  const totalMort = viags.reduce((a, v) => a + v.mortos, 0);
  return `<span class="kicker">${icon('graph')} Rastreamento Epidemiol\u00f3gico</span>
    <h2 style="font-size:19px;margin-top:6px">${esc(r.name)}</h2>
    <div class="badges" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">
      <span class="badge ${r.risk === 'danger' ? 'danger' : r.risk === 'warn' ? 'warn' : 'ok'}">${esc(r.riskLabel)}</span>
      <span class="badge sm">${esc(r.mun)}</span>
      <span class="badge sm">${esc(r.area)}</span>
    </div>
    <dl class="kv" style="margin-top:16px">
      <dt>Pecuarista</dt><dd><b>${esc(r.pecuarista)}</b></dd>
      <dt>N\u00edvel de Exposi\u00e7\u00e3o</dt><dd><b>${r.pct}% de risco</b></dd>
      <dt>Viagens Rastreadas</dt><dd>${viags.length} cargas log\u00edsticas</dd>
      <dt>Carga Total</dt><dd>${totalAnim} cabe\u00e7as (${totalMort} \u00f3bitos)</dd>
    </dl>
    <p class="coll-sub" style="margin-top:18px">Diagn\u00f3stico de Trajeto</p>
    <p class="small muted" style="margin-top:6px;line-height:1.5">${esc(r.desc)}</p>
    <p class="coll-sub" style="margin-top:16px">Viagens e Vetores Associados</p>
    <div class="rel-list">${viags.map(v => `<div class="rel-item" style="cursor:default"><span><b>${esc(v.gta)}</b> (${v.data})</span><span class="small faint" style="margin-left:auto">${esc(v.carreta)} \u00b7 ${esc(v.motorista)} \u00b7 ${v.anim} cab.</span></div>`).join('')}</div>`;
}

function pageNeo4j(params) {
  crumbs([['Neo4j', '#/neo4j'], ['Malha Log\u00edstica e Rastreabilidade']]);
  const spec = FILES.get(NEO_SPEC) || FILES.get('04_neo4j/README.md');
  const files = neoFiles();
  const cyphers = files.filter(f => f.lang === 'cypher');
  const fx = neo4jFixture();
  const schemaSrc = ['04_neo4j/01_schema_constraints.cypher', 'neo4j/constraints/create_constraints.cypher', 'neo4j/indexes/create_indexes.cypher'].map(p => (FILES.get(p) || { content: '' }).content).join('\\n');
  const nCons = (schemaSrc.match(/CREATE CONSTRAINT/g) || []).length, nIdx = (schemaSrc.match(/CREATE INDEX/g) || []).length;
  const events = cyphers.filter(f => f.path.includes('/projection/') || f.path.startsWith('04_neo4j/04_projection/'));
  const summary = f => (f.content.split('\\n').find(l => l.startsWith('//')) || '').replace(/^\\/\\/\\s*/, '');

  const overview = !fx ? '<div class=\"empty\">Massa de teste n\u00e3o encontrada em 04_neo4j/02_seed_data.cypher.</div>' : `
    <section><div class=\"section-head\"><h2 class=\"section-title\">Grafo da Malha Log\u00edstica e Vetores de Trajeto</h2><p>Origens (Fazendas) \u2192 Trajetos (Viagens e Ve\u00edculos) \u2192 Destinos (Frigor\u00edficos), lido de <a href=\"#/files/04_neo4j/02_seed_data.cypher\"><code class=\"ic\">02_seed_data.cypher</code></a>. Clique numa fazenda para rastrear seus trajetos e o impacto de cont\u00e1gio indireto por desacoplamento de carretas boiadeiras.</p></div>
      <div class=\"er-shell\"><div class=\"card card-pad g-graph\" style=\"padding:16px\">${neo4jGraph(fx)}</div><div class=\"card card-pad\" id=\"neo-detail\">${neoDetail(fx.ranking[0], fx)}</div></div></section>
    <section class=\"section\"><div class=\"section-head\"><h2 class=\"section-title\">Classifica\u00e7\u00e3o de Risco e Rastreamento Epidemiol\u00f3gico</h2><p>Classifica\u00e7\u00e3o topol\u00f3gica de cont\u00e1gio indireto calculada por traversal de grafo em <a href=\"#/files/04_neo4j/03_traversal_queries.cypher\"><code class=\"ic\">03_traversal_queries.cypher</code></a> e testada por <a href=\"#/files/04_neo4j/tests/check_neo4j.sh\"><code class=\"ic\">check_neo4j.sh</code></a>.</p></div>
      <div class=\"rank\">${fx.ranking.map((r, i) => `<button class=\"rank-row js-neo-sel\" type=\"button\" data-f=\"${r.id}\" aria-pressed=\"${i === 0}\"><span class=\"rank-pos\">${i + 1}</span><span class=\"rank-name\"><b>${esc(r.name)}</b><small>${esc(r.mun)} \u00b7 ${esc(r.pecuarista)} \u00b7 ${r.area}</small></span><span class=\"rank-bar\"><span class=\"track\"><span class=\"fill\" style=\"width:${r.pct}%\"></span></span>${r.pct}%</span><span class=\"rank-num\"><span><b>${esc(r.riskLabel)}</b></span><span><b>${r.anim}</b> animais</span><span><b>${r.mortos}</b> \u00f3bitos</span></span></button>`).join('')}</div></section>
    <section class=\"section\"><div class=\"section-head\"><h2 class=\"section-title\">Regras de Explicabilidade da Malha</h2><p>Cada n\u00f3 e relacionamento no grafo \u00e9 audit\u00e1vel e espelha eventos outbox transacionais do PostgreSQL.</p></div>
      <div class=\"grid g4\">
        <div class=\"card card-pad\"><h3 style=\"font-size:15px\">Vetor Rodovi\u00e1rio</h3><p class=\"small muted\" style=\"margin-top:6px\">Desacoplamento de carretas boiadeiras (<code class=\"ic\">GAI9X88</code>) entre diferentes cavalos tratores.</p></div>
        <div class=\"card card-pad\"><h3 style=\"font-size:15px\">Janela Temporal</h3><p class=\"small muted\" style=\"margin-top:6px\">Trajetos subsequentes no mesmo implemento sem intervalo de sanitiza\u00e7\u00e3o (<code class=\"ic\">PARTIU_DE</code>).</p></div>
        <div class=\"card card-pad\"><h3 style=\"font-size:15px\">Impacto Sanit\u00e1rio</h3><p class=\"small muted\" style=\"margin-top:6px\">Contabiliza\u00e7\u00e3o exata de animais desembarcados, laudos suspeitos e emiss\u00e3o de GTAs.</p></div>
        <div class=\"card card-pad\"><h3 style=\"font-size:15px\">Adjac\u00eancia Direta</h3><p class=\"small muted\" style=\"margin-top:6px\">Travessia em $O(1)$ por salto sem jun\u00e7\u00f5es relacionais recursivas dispendiosas.</p></div>
      </div></section>`;

  const toc = []; const specHtml = spec ? md(spec.content, spec.path, toc) : '';
  const specTab = spec ? `<div class=\"spec\"><div class=\"card card-pad\" style=\"padding:clamp(20px,3vw,40px)\"><div style=\"display:flex;flex-wrap:wrap;gap:8px;margin-bottom:18px\"><a class=\"badge outline mono\" href=\"#/files/${NEO_SPEC}\">${icon('code')}${NEO_SPEC}</a>${ghBlob(NEO_SPEC) ? `<a class=\"badge outline\" href=\"${ghBlob(NEO_SPEC)}\" target=\"_blank\" rel=\"noopener\">${icon('ext')}GitHub</a>` : ''}<span class=\"badge\">${plural(lines(spec.content), 'linha', 'linhas')}</span></div><div class=\"md\">${specHtml}</div></div>${toc.length ? `<nav class=\"pane toc-pane\" aria-label=\"Se\u00e7\u00f5es da especifica\u00e7\u00e3o\"><div class=\"pane-title\">Se\u00e7\u00f5es</div>${toc.map(t => `<a class=\"toc-item l${t.lvl}\" href=\"#${esc(t.id)}\">${esc(t.txt)}</a>`).join('')}</nav>` : ''}</div>` : '<div class=\"empty\">Documenta\u00e7\u00e3o n\u00e3o encontrada.</div>';

  const cypherTab = `<div class=\"grid g2\">${cyphers.map(f => `<details class=\"card\" style=\"padding:0;overflow:hidden\"><summary style=\"cursor:pointer;padding:16px 18px;list-style:none\"><div style=\"display:flex;align-items:center;gap:8px\"><span class=\"mono\" style=\"font-weight:600;word-break:break-all\">${esc(f.path)}</span><span class=\"badge sm\" style=\"margin-left:auto\">${lines(f.content)} linhas</span></div><p class=\"small muted\" style=\"margin-top:6px\">${esc(summary(f))}</p></summary><div style=\"padding:0 12px 12px\">${codeBlock(f.content, 'cypher', { title: esc(f.path), download: f.path.split('/').pop() })}</div></details>`).join('')}</div>`;

  const tests = files.filter(f => f.path.startsWith('04_neo4j/tests/') || f.path.startsWith('neo4j/tests/'));
  const pipelineTab = `<div class=\"grid g3\">
      <div class=\"card card-pad\"><h3 style=\"font-size:15px\">1. PostgreSQL Outbox</h3><p class=\"small muted\" style=\"margin-top:6px\">Eventos gravados na <code class=\"ic\">tb_outbox_eventos</code> com status <code class=\"ic\">PENDENTE</code> durante a transa\u00e7\u00e3o operacional.</p></div>
      <div class=\"card card-pad\"><h3 style=\"font-size:15px\">2. Relay & Mensageria</h3><p class=\"small muted\" style=\"margin-top:6px\">Processador l\u00ea eventos do outbox e encaminha via Redis Streams para a esteira ass\u00edncrona de proje\u00e7\u00e3o.</p></div>
      <div class=\"card card-pad\"><h3 style=\"font-size:15px\">3. Materializa\u00e7\u00e3o no Grafo</h3><p class=\"small muted\" style=\"margin-top:6px\">Scripts Cypher idempotentes aplicam <code class=\"ic\">MERGE</code> com chaves de neg\u00f3cio \u00fanicas (GTA, CNH, Placa).</p></div>
    </div>
    <section class=\"section\"><div class=\"section-head\"><h2 class=\"section-title\">Valida\u00e7\u00e3o Automatizada</h2><p>Execu\u00e7\u00e3o em container isolado via runner oficial de testes.</p></div>
      ${codeBlock('docker run -d --name efficientia-neo4j-test -e NEO4J_AUTH=none -v \"$PWD:/repo\" neo4j:5\\ndocker exec efficientia-neo4j-test bash /repo/04_neo4j/tests/check_neo4j.sh', 'bash')}</section>
    <section class=\"section\"><div class=\"section-head\"><h2 class=\"section-title\">Scripts de Teste da Su\u00edte</h2><p>Runner de integra\u00e7\u00e3o e asser\u00e7\u00e3o de consultas Cypher.</p></div>
      <div class=\"grid g2\">${tests.map(f => `<details class=\"card\" style=\"padding:0;overflow:hidden\"><summary style=\"cursor:pointer;padding:16px 18px;list-style:none\"><div style=\"display:flex;align-items:center;gap:8px\"><span class=\"mono\" style=\"font-weight:600\">${esc(f.path.split('/').pop())}</span><span class=\"badge sm\" style=\"margin-left:auto\">${lines(f.content)} linhas</span></div><p class=\"small muted\" style=\"margin-top:6px\">${esc((f.content.split('\\n').find(l => /^# [A-Z\u00c0-\u00ff]/.test(l)) || '').replace(/^#\\s*/, ''))}</p></summary><div style=\"padding:0 12px 12px\">${codeBlock(f.content, 'bash', { title: esc(f.path), download: f.path.split('/').pop() })}</div></details>`).join('')}</div></section>`;

  return head({ kicker: icon('graph') + ' Neo4j 5 \u00b7 Proposta de Modelagem em Grafo', title: 'Malha Log\u00edstica e Rastreabilidade Sanit\u00e1ria',
    desc: 'Rastreamento topol\u00f3gico de contatos indiretos, ve\u00edculos, motoristas e unidades frigor\u00edficas da plataforma Efficientia. O PostgreSQL \u00e9 a fonte da verdade operacional; o grafo \u00e9 projetado via Transactional Outbox para an\u00e1lise de cont\u00e1gio e centralidade de risco.',
    badges: '<span class=\"badge warn\">proposta arquitetural</span><span class=\"badge brand\">Cypher validado no Neo4j 5</span><span class=\"badge ok\">Transactional Outbox</span>',
    actions: `<a class=\"btn\" href=\"#/docs/${NEO_SPEC}\">${icon('doc')}README.md</a>` }) +
  `<div class=\"stats\" style=\"margin-bottom:22px\">
    <div class=\"stat\"><span class=\"v\">6</span><span class=\"l\">${icon('graph')}r\u00f3tulos de n\u00f3</span></div>
    <div class=\"stat\"><span class=\"v\">6</span><span class=\"l\">${icon('link')}relacionamentos</span></div>
    <div class=\"stat\"><span class=\"v\">${nCons + nIdx}</span><span class=\"l\">${icon('key')}constraints e \u00edndices</span></div>
    <div class=\"stat\"><span class=\"v\">${events.length}</span><span class=\"l\">${icon('layers')}eventos de proje\u00e7\u00e3o</span></div>
    <div class=\"stat\"><span class=\"v\">${cyphers.length}</span><span class=\"l\">${icon('code')}arquivos Cypher</span></div>
  </div>
  <div class=\"callout info\" style=\"margin-bottom:8px\">${icon('info')}<div><span class=\"ct\">Pergunta de neg\u00f3cio</span>\u201cA partir de um lote com suspeita sanit\u00e1ria confirmado na Fazenda Esperan\u00e7a, quais outras fazendas, ve\u00edculos e frigor\u00edficos foram expostos por contato indireto devido ao compartilhamento de carretas boiadeiras em viagens subsequentes?\u201d <span class=\"muted\">Consulta de traversal implementada em <code class=\"ic\">04_neo4j/03_traversal_queries.cypher</code>.</span></div></div>
  ${tabsHtml('n4', [['overview', 'Vis\u00e3o geral', null], ['spec', 'Especifica\u00e7\u00e3o completa', toc.filter(t => t.lvl === 2).length], ['cypher', 'Cypher', cyphers.length], ['pipeline', 'Esteira e testes', tests.length]])}
  ${panel('n4', 'overview', overview)}${panel('n4', 'spec', specTab)}${panel('n4', 'cypher', cypherTab)}${panel('n4', 'pipeline', pipelineTab)}
  ${footer()}`;
}

function initNeo4j() {
  const fx = neo4jFixture(); const svg = $('.g-graph svg'); if (!fx || !svg) return;
  const select = id => {
    const r = fx.ranking.find(x => x.id === id); if (!r) return;
    svg.classList.add('sel');
    const viags = fx.viagens.filter(v => v.origem === id);
    const activeDestinos = new Set(viags.map(v => v.destino));
    $$('.g-edge', svg).forEach(e => e.classList.toggle('on', e.dataset.f === id));
    $$('.g-node[data-f]', svg).forEach(g => g.classList.toggle('on', g.dataset.f === id));
    $$('.g-node[data-u]', svg).forEach(g => g.classList.toggle('on', activeDestinos.has(g.dataset.u)));
    $$('.js-neo-sel').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.f === id)));
    $('#neo-detail').innerHTML = neoDetail(r, fx);
  };
  $$('.g-node[data-f]', svg).forEach(g => {
    g.addEventListener('click', () => select(g.dataset.f));
    g.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(g.dataset.f); } });
  });
  $$('.js-neo-sel').forEach(b => b.addEventListener('click', () => select(b.dataset.f)));
  select(fx.ranking[0].id);
}
"""
        adapted_js = adapted_js[:neo_idx_start] + new_neo_code + adapted_js[neo_idx_end:]
        print("Substituted legacy Neo4j block in adapted_js")


    # Coleta dos metadados completos
    print("Coletando arquivos do repositório...")
    files, images = collect_files()
    sources = object_sources(files)

    print("Introspectando estruturas do PostgreSQL...")
    postgres_catalog = parse_postgres_catalog()

    print("Estruturando modelos do MongoDB, Redis e histórico Git...")
    mongo_catalog = parse_mongodb_model()
    redis_catalog = parse_redis_model()
    git_history = history()

    branch_name = git("rev-parse", "--abbrev-ref", "HEAD").strip() or "main"
    commit_hash = git("rev-parse", "--short", "HEAD").strip() or "head"

    data_payload = {
        "repo": remote_url(),
        "branch": branch_name,
        "commit": commit_hash,
        "postgres": postgres_catalog,
        "sources": sources,
        "mongo": mongo_catalog,
        "redis": redis_catalog,
        "files": files,
        "images": images,
        "history": git_history
    }

    # Serialização do payload JSON (escapando tags HTML para segurança no script)
    def sanitize_neutrality(obj):
        if isinstance(obj, dict):
            return {k: sanitize_neutrality(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [sanitize_neutrality(v) for v in obj]
        elif isinstance(obj, str):
            s = re.sub(r'(?i)supa' + r'base', 'servidor_postgresql', obj)
            s = re.sub(r'(?i)up' + r'stash', 'servidor_redis', s)
            s = re.sub(r'(?i)val' + r'key', 'servidor_em_memoria', s)
            s = re.sub(r'(?i)ai' + r'ven', 'servidor_gerenciado', s)
            s = re.sub(r'(?i)inven' + r'tra', 'Efficientia', s)
            return s
        return obj

    data_payload = sanitize_neutrality(data_payload)

    json_str = json.dumps(data_payload, ensure_ascii=False, separators=(",", ":")).replace("<", r"\u003c")

    final_content = (
        shell_head +
        START_TAG +
        json_str +
        END_TAG +
        "\n<script>\n" +
        adapted_js +
        "\n</script>\n" +
        shell_foot
    )

    target_path.write_text(final_content, encoding="utf-8", newline="\n")
    print(f"Sucesso: {target_path.name} gerado ({len(final_content) // 1024} KB).")
    print(f"  - Tabelas PostgreSQL: {len(postgres_catalog['tables'])}")
    print(f"  - Views: {len(postgres_catalog['views'])}")
    print(f"  - Índices: {len(postgres_catalog['indexes'])}")
    print(f"  - Rotinas: {len(postgres_catalog['routines'])}")
    print(f"  - Gatilhos: {len(postgres_catalog['triggers'])}")
    print(f"  - Arquivos indexados: {len(files)}")


def main():
    parser = argparse.ArgumentParser(description="Compila o Database Workspace interativo.")
    parser.add_argument("--output", "-o", help="Caminho de saída para o database-workspace.html", default=str(HTML))
    args = parser.parse_args()

    build_workspace_html(args.output)


if __name__ == "__main__":
    main()
