"""
Mecanismo central do RPA de Sincronização Bidirecional entre Banco 1 (Operacional) e Banco 2 (Corporativo).
Garante idempotência, resolução de chaves estrangeiras e integridade transacional.
"""

from __future__ import annotations
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy import text, inspect, Table, MetaData
from sqlalchemy.orm import Session

from config import settings
from database import DatabaseManager, db_manager
from mapper import (
    DataMapper,
    clean_cnpj,
    clean_cpf,
    clean_email,
    compute_content_hash,
    compute_empresa_hash,
    compute_motorista_hash,
)
from models import (
    DB1Empresa,
    DB1Motorista,
    DB2Endereco,
    DB2Empresa,
    DB2Usuario,
    RPASyncLog,
    BaseAudit,
)

logger = logging.getLogger("efficientia_rpa.syncer")


@dataclass
class SyncStats:
    """Estatísticas de uma direção de sincronização."""
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0


@dataclass
class SyncReport:
    """Relatório consolidado de um ciclo completo do RPA."""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_seconds: float = 0.0
    status: str = "SUCCESS"

    # Empresas
    empresa_db1_to_db2: SyncStats = field(default_factory=SyncStats)
    empresa_db2_to_db1: SyncStats = field(default_factory=SyncStats)

    # Motoristas / Caminhoneiros
    motorista_db1_to_db2: SyncStats = field(default_factory=SyncStats)
    motorista_db2_to_db1: SyncStats = field(default_factory=SyncStats)

    # Totais nos bancos
    total_db1_empresas: int = 0
    total_db2_empresas: int = 0
    total_db1_motoristas: int = 0
    total_db2_motoristas: int = 0

    logs: list[str] = field(default_factory=list)
    error_messages: list[str] = field(default_factory=list)

    def print_summary(self):
        """Imprime no terminal um resumo formatado da execução."""
        border = "=" * 78
        sub_border = "-" * 78
        print("\n" + border)
        print(f"  RELATÓRIO DE SINCRONIZAÇÃO RPA (DB1 (OPERACIONAL) ↔ DB2 (CORPORATIVO))")
        print(f"  Horário: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} UTC  |  Duração: {self.duration_seconds:.2f}s  |  Status: {self.status}")
        print(border)

        print(f"  ESTADO ATUAL DOS BANCOS DE DADOS:")
        print(f"    - Banco 1 (DB1 (Operacional) - Efficientia.sql):        {self.total_db1_empresas:4d} empresas | {self.total_db1_motoristas:4d} motoristas")
        print(f"    - Banco 2 (DB2 (Corporativo) - Efficientia-database): {self.total_db2_empresas:4d} empresas | {self.total_db2_motoristas:4d} motoristas/usuários")
        print(sub_border)

        print("  SINCRONIZAÇÃO DE EMPRESAS:")
        print(f"    [Banco 1 ➔ Banco 2] (DB1 ➔ DB2) Inseridos: {self.empresa_db1_to_db2.inserted:3d} | Atualizados: {self.empresa_db1_to_db2.updated:3d} | Inalterados: {self.empresa_db1_to_db2.skipped:3d} | Erros: {self.empresa_db1_to_db2.errors:3d}")
        print(f"    [Banco 2 ➔ Banco 1] (DB2 ➔ DB1) Inseridos: {self.empresa_db2_to_db1.inserted:3d} | Atualizados: {self.empresa_db2_to_db1.updated:3d} | Inalterados: {self.empresa_db2_to_db1.skipped:3d} | Erros: {self.empresa_db2_to_db1.errors:3d}")
        print(sub_border)

        print("  SINCRONIZAÇÃO DE CAMINHONEIROS / MOTORISTAS:")
        print(f"    [Banco 1 ➔ Banco 2] (DB1 ➔ DB2) Inseridos: {self.motorista_db1_to_db2.inserted:3d} | Atualizados: {self.motorista_db1_to_db2.updated:3d} | Inalterados: {self.motorista_db1_to_db2.skipped:3d} | Erros: {self.motorista_db1_to_db2.errors:3d}")
        print(f"    [Banco 2 ➔ Banco 1] (DB2 ➔ DB1) Inseridos: {self.motorista_db2_to_db1.inserted:3d} | Atualizados: {self.motorista_db2_to_db1.updated:3d} | Inalterados: {self.motorista_db2_to_db1.skipped:3d} | Erros: {self.motorista_db2_to_db1.errors:3d}")
        print(border)

        if self.error_messages:
            print("  ⚠️  ERROS DETECTADOS:")
            for err in self.error_messages:
                print(f"    * {err}")
            print(border)
        print()


class DatabaseSyncer:
    """Orquestrador do RPA de sincronização bidirecional entre Instancia Operacional (DB1) e Instancia Corporativa (DB2)."""

    def __init__(self, manager: DatabaseManager | None = None, dry_run: bool = False):
        self.mgr = manager or db_manager
        self.dry_run = dry_run
        self.db1_motorista_has_cpf = False
        self._check_schema_capabilities()

    def _check_schema_capabilities(self):
        """Inspeciona colunas opcionais existentes nos bancos."""
        cols_db1 = self.mgr.inspect_columns(self.mgr.engine_db1, settings.db1_motorista_table)
        self.db1_motorista_has_cpf = "cpf" in cols_db1
    def get_or_create_default_endereco(self, session2: Session) -> str:
        """Garante a existência de ao menos um endereço em sc_corporativo.tb_endereco para FK de empresas."""
        end = session2.query(DB2Endereco).first()
        if not end:
            end = DB2Endereco(
                id=str(uuid.uuid4()),
                cep="01001-000",
                logradouro="Logradouro Operacional Matriz",
                numero="S/N",
                cidade="São Paulo",
                estado="SP",
            )
            session2.add(end)
            session2.flush()
        return str(end.id)


    def ensure_audit_tables(self):
        """Cria as tabelas de auditoria do RPA caso não existam."""
        if not self.dry_run:
            try:
                BaseAudit.metadata.create_all(self.mgr.engine_db2, checkfirst=True)
            except Exception as e:
                logger.warning(f"Erro ao verificar tabela de auditoria no DB2: {e}")
            try:
                BaseAudit.metadata.create_all(self.mgr.engine_db1, checkfirst=True)
            except Exception as e:
                logger.warning(f"Erro ao verificar tabela de auditoria no DB1: {e}")

    def log_audit(
        self,
        session_audit: Session,
        entity_type: str,
        source_db: str,
        target_db: str,
        source_id: Any,
        target_id: Any,
        natural_key: str,
        action: str,
        data_hash: str | None = None,
        error_message: str | None = None,
    ):
        """Registra ação na tabela de auditoria."""
        if self.dry_run:
            return
        try:
            entry = RPASyncLog(
                entity_type=entity_type,
                source_db=source_db,
                target_db=target_db,
                source_id=str(source_id),
                target_id=str(target_id) if target_id is not None else None,
                natural_key=natural_key,
                action=action,
                data_hash=data_hash,
                error_message=error_message,
            )
            session_audit.add(entry)
        except Exception as e:
            logger.warning(f"Não foi possível gravar log de auditoria: {e}")

    # ==========================================================================
    # SINCRONIZAÇÃO DE EMPRESAS
    # ==========================================================================
    def sync_empresas(
        self,
        session1: Session,
        session2: Session,
        report: SyncReport,
    ) -> tuple[dict[int, int], dict[int, int]]:
        """
        Executa a sincronização bidirecional das tabelas 'empresa'.
        Retorna dicionários de mapeamento cruzado de IDs de empresas:
          (db1_to_db2_id, db2_to_db1_id)
        """
        logger.info("Iniciando sincronização de EMPRESAS...")

        # 1. Carrega todas as empresas do Banco 1 (Operacional)
        db1_empresas = session1.query(DB1Empresa).all()
        db1_by_cnpj: dict[str, DB1Empresa] = {}
        db1_by_codigo: dict[str, DB1Empresa] = {}

        for emp in db1_empresas:
            cnpj_clean = clean_cnpj(emp.cnpj)
            if cnpj_clean:
                db1_by_cnpj[cnpj_clean] = emp
            if emp.codigo:
                db1_by_codigo[emp.codigo.strip()] = emp

        # 2. Carrega todas as empresas do Banco 2 (Corporativo)
        db2_empresas = session2.query(DB2Empresa).all()
        db2_by_cnpj: dict[str, DB2Empresa] = {}
        db2_by_codigo: dict[str, DB2Empresa] = {}

        for emp in db2_empresas:
            cnpj_clean = clean_cnpj(emp.cnpj)
            if cnpj_clean:
                db2_by_cnpj[cnpj_clean] = emp
            if emp.codigo_interno:
                db2_by_codigo[emp.codigo_interno.strip()] = emp

        # Carrega histórico de hashes de empresas para idempotência e deltas
        audit_emp_logs = []
        try:
            audit_emp_logs = (
                session2.query(RPASyncLog)
                .filter(RPASyncLog.entity_type == "empresa")
                .order_by(RPASyncLog.id.asc())
                .all()
            )
        except Exception:
            try:
                audit_emp_logs = (
                    session1.query(RPASyncLog)
                    .filter(RPASyncLog.entity_type == "empresa")
                    .order_by(RPASyncLog.id.asc())
                    .all()
                )
            except Exception:
                pass

        last_empresa_hash: dict[str, str] = {
            log.natural_key: log.data_hash for log in audit_emp_logs if log.data_hash
        }

        db1_to_db2_id: dict[int, int] = {}
        db2_to_db1_id: dict[int, int] = {}

        # ----------------------------------------------------------------------
        # A) Banco 1 ➔ Banco 2 (Puxar empresas do DB1 (Operacional) para o DB2 (Corporativo))
        # ----------------------------------------------------------------------
        for emp1 in db1_empresas:
            cnpj_clean = clean_cnpj(emp1.cnpj)
            emp2_match = db2_by_cnpj.get(cnpj_clean) or (db2_by_codigo.get(emp1.codigo.strip()) if emp1.codigo else None)

            source_dict = {
                "id": emp1.id,
                "nome": emp1.nome,
                "cnpj": emp1.cnpj,
                "codigo": emp1.codigo,
            }
            mapped = DataMapper.empresa_db1_to_db2(
                source_dict,
                default_password_hash=settings.default_sync_password_hash
            )
            data_hash = compute_empresa_hash(emp1.nome, emp1.cnpj, emp1.codigo)

            if not emp2_match:
                # INSERT em Banco 2 (Corporativo)
                logger.info(f"[DB1 ➔ DB2] Inserindo nova empresa no DB2 (Corporativo): CNPJ={cnpj_clean}, Nome='{emp1.nome}'")
                if not self.dry_run:
                    end_id = self.get_or_create_default_endereco(session2)
                    novo_emp2 = DB2Empresa(
                        id=str(uuid.uuid4()),
                        endereco_id=end_id,
                        nome=mapped["nome"],
                        razao_social=mapped.get("razao_social") or mapped["nome"],
                        codigo_interno=mapped["codigo_interno"],
                        cnpj=mapped["cnpj"],
                        email=mapped.get("email"),
                    )
                    session2.add(novo_emp2)
                    session2.flush()
                    db2_by_cnpj[cnpj_clean] = novo_emp2
                    if novo_emp2.codigo_interno:
                        db2_by_codigo[novo_emp2.codigo_interno] = novo_emp2
                    db1_to_db2_id[emp1.id] = novo_emp2.id
                    db2_to_db1_id[novo_emp2.id] = emp1.id
                    self.log_audit(
                        session2, "empresa", "db1", "db2",
                        emp1.id, novo_emp2.id, cnpj_clean, "INSERT", data_hash
                    )
                    last_empresa_hash[cnpj_clean] = data_hash
                else:
                    db1_to_db2_id[emp1.id] = emp1.id
                    db2_to_db1_id[emp1.id] = emp1.id
                report.empresa_db1_to_db2.inserted += 1
            else:
                db1_to_db2_id[emp1.id] = emp2_match.id
                db2_to_db1_id[emp2_match.id] = emp1.id
                # Verificar divergências para UPDATE
                cur_dict = {
                    "nome": emp2_match.nome,
                    "codigo_interno": emp2_match.codigo_interno,
                }
                diffs = DataMapper.get_divergences(cur_dict, mapped, ["nome", "codigo_interno"])
                if diffs:
                    last_hash = last_empresa_hash.get(cnpj_clean)
                    if last_hash and data_hash == last_hash:
                        report.empresa_db1_to_db2.skipped += 1
                        continue

                    logger.info(f"[DB1 ➔ DB2] Atualizando empresa ID={emp2_match.id} no DB2 (Corporativo) (CNPJ={cnpj_clean}): {diffs}")
                    if not self.dry_run:
                        if "nome" in diffs:
                            emp2_match.nome = mapped["nome"]
                            emp2_match.razao_social = mapped["razao_social"]
                        if "codigo_interno" in diffs:
                            emp2_match.codigo_interno = mapped["codigo_interno"]
                        session2.flush()
                        self.log_audit(
                            session2, "empresa", "db1", "db2",
                            emp1.id, emp2_match.id, cnpj_clean, "UPDATE", data_hash
                        )
                        last_empresa_hash[cnpj_clean] = data_hash
                    report.empresa_db1_to_db2.updated += 1
                else:
                    report.empresa_db1_to_db2.skipped += 1

        if not self.dry_run:
            session2.commit()

        # ----------------------------------------------------------------------
        # B) Banco 2 ➔ Banco 1 (Puxar empresas do DB2 (Corporativo) para o DB1 (Operacional))
        # ----------------------------------------------------------------------
        db2_empresas = session2.query(DB2Empresa).all()
        for emp2 in db2_empresas:
            cnpj_clean = clean_cnpj(emp2.cnpj)
            emp1_match = db1_by_cnpj.get(cnpj_clean) or (db1_by_codigo.get(emp2.codigo_interno.strip()) if emp2.codigo_interno else None)

            source_dict = {
                "id": emp2.id,
                "nome": emp2.nome,
                "razao_social": emp2.razao_social,
                "cnpj": emp2.cnpj,
                "codigo_interno": emp2.codigo_interno,
            }
            mapped = DataMapper.empresa_db2_to_db1(source_dict)
            data_hash = compute_empresa_hash(emp2.nome, emp2.cnpj, emp2.codigo_interno)

            if not emp1_match:
                # INSERT no Banco 1 (Operacional)
                logger.info(f"[DB2 ➔ DB1] Inserindo nova empresa no DB1 (Operacional): CNPJ={cnpj_clean}, Nome='{mapped['nome']}'")
                if not self.dry_run:
                    novo_emp1 = DB1Empresa(
                        nome=mapped["nome"],
                        cnpj=mapped["cnpj"],
                        codigo=mapped["codigo"],
                    )
                    session1.add(novo_emp1)
                    session1.flush()
                    db1_by_cnpj[cnpj_clean] = novo_emp1
                    if novo_emp1.codigo:
                        db1_by_codigo[novo_emp1.codigo] = novo_emp1
                    db2_to_db1_id[emp2.id] = novo_emp1.id
                    db1_to_db2_id[novo_emp1.id] = emp2.id
                    self.log_audit(
                        session2, "empresa", "db2", "db1",
                        emp2.id, novo_emp1.id, cnpj_clean, "INSERT", data_hash
                    )
                    last_empresa_hash[cnpj_clean] = data_hash
                report.empresa_db2_to_db1.inserted += 1
            else:
                db2_to_db1_id[emp2.id] = emp1_match.id
                db1_to_db2_id[emp1_match.id] = emp2.id
                # Verificar divergências para UPDATE
                cur_dict = {
                    "nome": emp1_match.nome,
                    "codigo": emp1_match.codigo,
                }
                diffs = DataMapper.get_divergences(cur_dict, mapped, ["nome", "codigo"])
                if diffs:
                    last_hash = last_empresa_hash.get(cnpj_clean)
                    if last_hash and data_hash == last_hash:
                        report.empresa_db2_to_db1.skipped += 1
                        continue

                    logger.info(f"[DB2 ➔ DB1] Atualizando empresa ID={emp1_match.id} no DB1 (Operacional) (CNPJ={cnpj_clean}): {diffs}")
                    if not self.dry_run:
                        if "nome" in diffs:
                            emp1_match.nome = mapped["nome"]
                        if "codigo" in diffs:
                            emp1_match.codigo = mapped["codigo"]
                        session1.flush()
                        self.log_audit(
                            session2, "empresa", "db2", "db1",
                            emp2.id, emp1_match.id, cnpj_clean, "UPDATE", data_hash
                        )
                        last_empresa_hash[cnpj_clean] = data_hash
                    report.empresa_db2_to_db1.updated += 1
                else:
                    report.empresa_db2_to_db1.skipped += 1

        if not self.dry_run:
            session1.commit()
            session2.commit()
        # ----------------------------------------------------------------------
        # C) Constrói mapeamento cruzado de IDs de empresas (FK Resolution)
        # ----------------------------------------------------------------------
        db1_empresas_final = session1.query(DB1Empresa).all()
        db2_empresas_final = session2.query(DB2Empresa).all()

        if not self.dry_run:
            db1_to_db2_id.clear()
            db2_to_db1_id.clear()

        temp_db2_map = {clean_cnpj(e.cnpj): e.id for e in db2_empresas_final if clean_cnpj(e.cnpj)}
        temp_db2_cod_map = {e.codigo_interno.strip(): e.id for e in db2_empresas_final if e.codigo_interno}

        for e1 in db1_empresas_final:
            cnpj1 = clean_cnpj(e1.cnpj)
            e2_id = temp_db2_map.get(cnpj1) or (temp_db2_cod_map.get(e1.codigo.strip()) if e1.codigo else None)
            if e2_id:
                db1_to_db2_id[e1.id] = e2_id
                db2_to_db1_id[e2_id] = e1.id

        report.total_db1_empresas = len(db1_empresas_final)
        report.total_db2_empresas = len(db2_empresas_final)

        return db1_to_db2_id, db2_to_db1_id

    # ==========================================================================
    # SINCRONIZAÇÃO DE CAMINHONEIROS / MOTORISTAS
    # ==========================================================================
    def sync_caminhoneiros(
        self,
        session1: Session,
        session2: Session,
        db1_to_db2_empresa: dict[int, int],
        db2_to_db1_empresa: dict[int, int],
        report: SyncReport,
    ):
        """
        Executa a sincronização bidirecional de motoristas/caminhoneiros.
        No Banco 1 (Operacional): tabela 'motorista'.
        No Banco 2 (Corporativo): tabela 'usuario' com tipo='motorista'.
        """
        logger.info("Iniciando sincronização de CAMINHONEIROS / MOTORISTAS...")

        # 1. Carrega todos os motoristas do Banco 1 (Operacional)
        db1_motoristas = session1.query(DB1Motorista).all()
        db1_by_email: dict[str, DB1Motorista] = {}
        db1_by_cpf: dict[str, DB1Motorista] = {}
        db1_by_nome_empresa: dict[tuple[str, int], DB1Motorista] = {}

        for mot in db1_motoristas:
            email_clean = clean_email(mot.email)
            if email_clean:
                db1_by_email[email_clean] = mot
            if hasattr(mot, "cpf") and mot.cpf:
                cpf_clean = clean_cpf(mot.cpf)
                if cpf_clean:
                    db1_by_cpf[cpf_clean] = mot
            if mot.nome and mot.id_empresa:
                db1_by_nome_empresa[(mot.nome.strip().lower(), mot.id_empresa)] = mot

        # 2. Carrega todos os motoristas do Banco 2 (Corporativo)
        db2_motoristas = session2.query(DB2Usuario).filter(DB2Usuario.tipo == "motorista").all()
        db2_by_cpf: dict[str, DB2Usuario] = {}
        db2_by_email: dict[str, DB2Usuario] = {}
        db2_by_nome_empresa: dict[tuple[str, int | None], DB2Usuario] = {}

        for mot in db2_motoristas:
            cpf_clean = clean_cpf(mot.cpf)
            email_clean = clean_email(mot.email)
            if cpf_clean:
                db2_by_cpf[cpf_clean] = mot
            if email_clean:
                db2_by_email[email_clean] = mot
            if mot.nome:
                db2_by_nome_empresa[(mot.nome.strip().lower(), mot.empresa_id)] = mot

        report.total_db1_motoristas = len(db1_motoristas)
        report.total_db2_motoristas = len(db2_motoristas)

        # Histórico de hashes
        audit_mot_logs = []
        try:
            audit_mot_logs = (
                session2.query(RPASyncLog)
                .filter(RPASyncLog.entity_type == "motorista")
                .order_by(RPASyncLog.id.asc())
                .all()
            )
        except Exception:
            try:
                audit_mot_logs = (
                    session1.query(RPASyncLog)
                    .filter(RPASyncLog.entity_type == "motorista")
                    .order_by(RPASyncLog.id.asc())
                    .all()
                )
            except Exception:
                pass

        last_mot_hash: dict[str, str] = {
            log.natural_key: log.data_hash for log in audit_mot_logs if log.data_hash
        }

        # ----------------------------------------------------------------------
        # A) Banco 1 ➔ Banco 2 (Puxar motoristas do DB1 (Operacional) para o DB2 (Corporativo))
        # ----------------------------------------------------------------------
        for mot1 in db1_motoristas:
            target_emp2_id = db1_to_db2_empresa.get(mot1.id_empresa)
            if not target_emp2_id:
                if db1_to_db2_empresa:
                    target_emp2_id = list(db1_to_db2_empresa.values())[0]
                else:
                    msg = f"[DB1 ➔ DB2] Nenhuma empresa disponível no DB2 (Corporativo) para vincular o motorista '{mot1.nome}'"
                    logger.warning(msg)
                    report.error_messages.append(msg)
                    report.motorista_db1_to_db2.errors += 1
                    continue

            source_dict = {
                "id": mot1.id,
                "id_empresa": mot1.id_empresa,
                "nome": mot1.nome,
                "data_nascimento": mot1.data_nascimento,
                "email": mot1.email,
                "telefone": mot1.telefone,
                "senha": mot1.senha,
                "cpf": getattr(mot1, "cpf", None),
            }
            mapped = DataMapper.motorista_db1_to_db2(
                source_dict,
                target_empresa_id=target_emp2_id,
                default_password_hash=settings.default_sync_password_hash,
            )
            mot_email = clean_email(mot1.email)
            mot_cpf = clean_cpf(getattr(mot1, "cpf", None))
            mot_key = mot_email or mot_cpf or (mot1.nome or "").strip().lower()
            data_hash = compute_motorista_hash(
                mot1.nome, mot_email, mot1.telefone, mot1.data_nascimento
            )

            # Busca no DB2 (Corporativo) por CPF, Email ou (Nome, Empresa)
            mot2_match: Optional[DB2Usuario] = None
            if mapped.get("cpf") and mapped["cpf"] in db2_by_cpf:
                mot2_match = db2_by_cpf[mapped["cpf"]]
            elif mapped.get("email") and mapped["email"] in db2_by_email:
                mot2_match = db2_by_email[mapped["email"]]
            else:
                mot2_match = db2_by_nome_empresa.get((mapped["nome"].strip().lower(), target_emp2_id))

            if not mot2_match:
                # INSERT no DB2 (Corporativo)
                logger.info(f"[DB1 ➔ DB2] Inserindo motorista no DB2 (Corporativo): Nome='{mapped['nome']}', EmpresaID={target_emp2_id}")
                if not self.dry_run:
                    novo_mot2 = DB2Usuario(
                        id=str(uuid.uuid4()),
                        empresa_id=target_emp2_id,
                        tipo="motorista",
                        cargo="Motorista",
                        nivel_acesso="conducao",
                        cpf=mapped["cpf"],
                        nome_completo=mapped["nome"],
                        data_nascimento=mapped.get("data_nascimento"),
                        email=mapped.get("email"),
                        telefone=mapped.get("telefone"),
                        senha_hash=mapped.get("senha_hash") or self.default_password_hash,
                        status_cadastro="ativo",
                    )
                    session2.add(novo_mot2)
                    session2.flush()
                    if mapped.get("cpf"):
                        db2_by_cpf[mapped["cpf"]] = novo_mot2
                    if mapped.get("email"):
                        db2_by_email[mapped["email"]] = novo_mot2
                    db2_by_nome_empresa[(mapped["nome"].strip().lower(), target_emp2_id)] = novo_mot2
                    self.log_audit(
                        session2, "motorista", "db1", "db2",
                        mot1.id, novo_mot2.id, mot_key, "INSERT", data_hash
                    )
                    last_mot_hash[mot_key] = data_hash
                    if mot_email:
                        last_mot_hash[mot_email] = data_hash
                    if mot_cpf:
                        last_mot_hash[mot_cpf] = data_hash
                report.motorista_db1_to_db2.inserted += 1
            else:
                # Verificar divergências para UPDATE
                cur_dict = {
                    "nome": mot2_match.nome,
                    "telefone": mot2_match.telefone,
                    "data_nascimento": mot2_match.data_nascimento,
                }
                diffs = DataMapper.get_divergences(cur_dict, mapped, ["nome", "telefone", "data_nascimento"])
                if diffs:
                    last_hash = last_mot_hash.get(mot_key) or (last_mot_hash.get(mot_email) if mot_email else None)
                    if last_hash and data_hash == last_hash:
                        report.motorista_db1_to_db2.skipped += 1
                        continue

                    logger.info(f"[DB1 ➔ DB2] Atualizando motorista ID={mot2_match.id} no DB2 (Corporativo) ('{mot2_match.nome}'): {diffs}")
                    if not self.dry_run:
                        if "nome" in diffs:
                            mot2_match.nome = mapped["nome"]
                        if "telefone" in diffs:
                            mot2_match.telefone = mapped["telefone"]
                        if "data_nascimento" in diffs:
                            mot2_match.data_nascimento = mapped["data_nascimento"]
                        session2.flush()
                        self.log_audit(
                            session2, "motorista", "db1", "db2",
                            mot1.id, mot2_match.id, mot_key, "UPDATE", data_hash
                        )
                        last_mot_hash[mot_key] = data_hash
                        if mot_email:
                            last_mot_hash[mot_email] = data_hash
                        if mot_cpf:
                            last_mot_hash[mot_cpf] = data_hash
                    report.motorista_db1_to_db2.updated += 1
                else:
                    report.motorista_db1_to_db2.skipped += 1

        if not self.dry_run:
            session2.commit()

        # ----------------------------------------------------------------------
        # B) Banco 2 ➔ Banco 1 (Puxar motoristas do DB2 (Corporativo) para o DB1 (Operacional))
        # ----------------------------------------------------------------------
        db2_motoristas = session2.query(DB2Usuario).filter(DB2Usuario.tipo == "motorista").all()

        for mot2 in db2_motoristas:
            target_emp1_id = db2_to_db1_empresa.get(mot2.empresa_id) if mot2.empresa_id else None
            if not target_emp1_id:
                if db2_to_db1_empresa:
                    target_emp1_id = list(db2_to_db1_empresa.values())[0]
                else:
                    msg = f"[DB2 ➔ DB1] Não há empresas cadastradas no DB1 (Operacional) para vincular o motorista '{mot2.nome}'"
                    logger.warning(msg)
                    report.error_messages.append(msg)
                    report.motorista_db2_to_db1.errors += 1
                    continue

            source_dict = {
                "id": mot2.id,
                "empresa_id": mot2.empresa_id,
                "nome": mot2.nome,
                "cpf": mot2.cpf,
                "email": mot2.email,
                "telefone": mot2.telefone,
                "data_nascimento": mot2.data_nascimento,
                "senha_hash": mot2.senha_hash,
                "url_assinatura_geral": getattr(mot2, "url_assinatura_geral", None),
            }
            mapped = DataMapper.motorista_db2_to_db1(source_dict, target_empresa_id=target_emp1_id)
            mot_email = clean_email(mot2.email)
            mot_cpf = clean_cpf(mot2.cpf)
            mot_key = mot_email or mot_cpf or (mot2.nome or "").strip().lower()
            data_hash = compute_motorista_hash(
                mot2.nome, mot_email, mot2.telefone, mot2.data_nascimento
            )

            # Busca no DB1 (Operacional) por CPF (se suportado), Email ou (Nome, Empresa)
            mot1_match: Optional[DB1Motorista] = None
            if mapped.get("cpf") and mapped["cpf"] in db1_by_cpf:
                mot1_match = db1_by_cpf[mapped["cpf"]]
            elif mapped.get("email") and mapped["email"] in db1_by_email:
                mot1_match = db1_by_email[mapped["email"]]
            else:
                mot1_match = db1_by_nome_empresa.get((mapped["nome"].strip().lower(), target_emp1_id))

            if not mot1_match:
                # INSERT no DB1 (Operacional)
                logger.info(f"[DB2 ➔ DB1] Inserindo motorista no DB1 (Operacional): Nome='{mapped['nome']}', EmpresaID={target_emp1_id}")
                if not self.dry_run:
                    mot1_kwargs = {
                        "id_empresa": mapped["id_empresa"],
                        "nome": mapped["nome"],
                        "data_nascimento": mapped["data_nascimento"] or datetime.now().date(),
                        "email": mapped["email"],
                        "telefone": mapped["telefone"] or "11999999999",
                        "senha": mapped["senha"] or "senha123",
                        "assinatura": mapped["assinatura"],
                    }
                    if self.db1_motorista_has_cpf and hasattr(DB1Motorista, "cpf"):
                        mot1_kwargs["cpf"] = mapped["cpf"]

                    novo_mot1 = DB1Motorista(**mot1_kwargs)
                    session1.add(novo_mot1)
                    session1.flush()
                    if mapped.get("email"):
                        db1_by_email[mapped["email"]] = novo_mot1
                    if mapped.get("cpf"):
                        db1_by_cpf[mapped["cpf"]] = novo_mot1
                    db1_by_nome_empresa[(mapped["nome"].strip().lower(), target_emp1_id)] = novo_mot1
                    self.log_audit(
                        session2, "motorista", "db2", "db1",
                        mot2.id, novo_mot1.id, mot_key, "INSERT", data_hash
                    )
                    last_mot_hash[mot_key] = data_hash
                    if mot_email:
                        last_mot_hash[mot_email] = data_hash
                    if mot_cpf:
                        last_mot_hash[mot_cpf] = data_hash
                report.motorista_db2_to_db1.inserted += 1
            else:
                # Verificar divergências para UPDATE
                cur_dict = {
                    "nome": mot1_match.nome,
                    "telefone": mot1_match.telefone,
                    "data_nascimento": mot1_match.data_nascimento,
                    "id_empresa": mot1_match.id_empresa,
                }
                diffs = DataMapper.get_divergences(cur_dict, mapped, ["nome", "telefone", "data_nascimento", "id_empresa"])
                if diffs:
                    last_hash = last_mot_hash.get(mot_key) or (last_mot_hash.get(mot_email) if mot_email else None)
                    if last_hash and data_hash == last_hash:
                        report.motorista_db2_to_db1.skipped += 1
                        continue

                    logger.info(f"[DB2 ➔ DB1] Atualizando motorista ID={mot1_match.id} no DB1 (Operacional) ('{mot1_match.nome}'): {diffs}")
                    if not self.dry_run:
                        if "nome" in diffs:
                            mot1_match.nome = mapped["nome"]
                        if "telefone" in diffs:
                            mot1_match.telefone = mapped["telefone"]
                        if "data_nascimento" in diffs:
                            mot1_match.data_nascimento = mapped["data_nascimento"]
                        if "id_empresa" in diffs:
                            mot1_match.id_empresa = mapped["id_empresa"]
                        session1.flush()
                        self.log_audit(
                            session2, "motorista", "db2", "db1",
                            mot2.id, mot1_match.id, mot_key, "UPDATE", data_hash
                        )
                        last_mot_hash[mot_key] = data_hash
                        if mot_email:
                            last_mot_hash[mot_email] = data_hash
                        if mot_cpf:
                            last_mot_hash[mot_cpf] = data_hash
                    report.motorista_db2_to_db1.updated += 1
                else:
                    report.motorista_db2_to_db1.skipped += 1

        if not self.dry_run:
            session1.commit()
            session2.commit()
        # Atualiza totais finais
        report.total_db1_motoristas = session1.query(DB1Motorista).count()
        report.total_db2_motoristas = session2.query(DB2Usuario).filter(DB2Usuario.tipo == "motorista").count()

    # ==========================================================================
    # CICLO COMPLETO DE SINCRONIZAÇÃO BIDIRECIONAL
    # ==========================================================================
    def run_sync_cycle(self) -> SyncReport:
        """Executa um ciclo completo de sincronização bidirecional entre Instancia Operacional (DB1) e Instancia Corporativa (DB2)."""
        start_time = time.time()
        report = SyncReport()

        logger.info("=== INICIANDO CICLO DE SINCRONIZAÇÃO BIDIRECIONAL DO RPA ===")
        if self.dry_run:
            logger.info("MODO DRY-RUN ATIVADO: Nenhuma gravação real será realizada.")

        session1 = self.mgr.get_db1_session()
        session2 = self.mgr.get_db2_session()

        try:
            self.ensure_audit_tables()

            # 1. Sincroniza Empresas e obtém mapeamento cruzado de chaves
            db1_to_db2_empresa, db2_to_db1_empresa = self.sync_empresas(session1, session2, report)

            # 2. Sincroniza Caminhoneiros / Motoristas usando as chaves resolvidas
            self.sync_caminhoneiros(session1, session2, db1_to_db2_empresa, db2_to_db1_empresa, report)

            report.status = "SUCCESS" if not report.error_messages else "WARNING"
        except Exception as e:
            logger.exception(f"Erro fatal no ciclo de sincronização: {e}")
            session1.rollback()
            session2.rollback()
            report.status = "ERROR"
            report.error_messages.append(str(e))
        finally:
            session1.close()
            session2.close()
            report.duration_seconds = time.time() - start_time
            logger.info(f"=== CICLO DE SINCRONIZAÇÃO FINALIZADO EM {report.duration_seconds:.2f}s (STATUS: {report.status}) ===")

        return report
