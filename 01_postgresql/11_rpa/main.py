"""
Ponto de entrada (CLI) do RPA de Sincronização Bidirecional entre Banco 1 e Banco 2.
"""

from __future__ import annotations
import argparse
import logging
import sys
import time

from config import settings
from database import db_manager
from init_schemas import create_all_tables, seed_sample_data
from models import DB1Empresa, DB1Motorista, DB2Empresa, DB2Usuario, RPASyncLog
from syncer import DatabaseSyncer
logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("efficientia_rpa.main")


def cmd_run(args):
    """Executa um ciclo único de sincronização bidirecional."""
    syncer = DatabaseSyncer(dry_run=args.dry_run)
    report = syncer.run_sync_cycle()
    report.print_summary()
    return 0 if report.status != "ERROR" else 1


def cmd_daemon(args):
    """Executa o RPA em modo daemon (loop contínuo)."""
    interval = args.interval or settings.sync_interval_seconds
    logger.info(f"Iniciando RPA em modo DAEMON (intervalo: {interval}s). Pressione Ctrl+C para encerrar.")
    syncer = DatabaseSyncer(dry_run=args.dry_run)

    cycle_count = 1
    try:
        while True:
            logger.info(f"--- Ciclo #{cycle_count} ---")
            report = syncer.run_sync_cycle()
            report.print_summary()
            cycle_count += 1
            logger.info(f"Aguardando {interval} segundos até o próximo ciclo...")
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Execução interrompida pelo usuário. Encerrando daemon...")
        return 0


def cmd_init_db(args):
    """Inicializa as tabelas nos dois bancos e opcionalmente adiciona dados de teste."""
    logger.info("Inicializando estruturas de banco de dados...")
    create_all_tables()
    if args.seed:
        seed_sample_data()
    logger.info("Bancos inicializados com sucesso!")
    return 0


def cmd_stats(args):
    """Exibe o estado e estatísticas atuais de ambos os bancos."""
    session1 = db_manager.get_db1_session()
    session2 = db_manager.get_db2_session()

    try:
        emp1_list = session1.query(DB1Empresa).all()
        mot1_list = session1.query(DB1Motorista).all()

        emp2_list = session2.query(DB2Empresa).all()
        mot2_list = session2.query(DB2Usuario).filter(DB2Usuario.tipo == "motorista").all()

        print("\n" + "=" * 80)
        print("                   ESTADO DOS BANCOS DE DADOS")
        print("=" * 80)

        print(f"\n[BANCO 1 - DB1 (Operacional) (Efficientia.sql - Logística)] - Total Empresas: {len(emp1_list)} | Total Motoristas: {len(mot1_list)}")
        print("-" * 80)
        print("  EMPRESAS:")
        for e in emp1_list:
            print(f"    * ID={e.id:<3} | CNPJ={e.cnpj:<14} | Cód={e.codigo or '-':<12} | Nome: {e.nome}")
        print("  MOTORISTAS / CAMINHONEIROS:")
        for m in mot1_list:
            print(f"    * ID={m.id:<3} | EmpID={m.id_empresa or '-':<3} | Email={m.email or '-':<28} | Nome: {m.nome}")

        print(f"\n[BANCO 2 - DB2 (Corporativo) (Efficientia-database - Corporativo)] - Total Empresas: {len(emp2_list)} | Total Motoristas: {len(mot2_list)}")
        print("-" * 80)
        print("  EMPRESAS:")
        for e in emp2_list:
            print(f"    * ID={str(e.id):<36} | CNPJ={e.cnpj:<14} | Cód={e.codigo_interno or '-':<12} | Nome: {e.nome}")
        print("  MOTORISTAS / CAMINHONEIROS:")
        for m in mot2_list:
            nome_exibir = getattr(m, "nome_completo", getattr(m, "nome", "Sem Nome"))
            print(f"    * ID={str(m.id):<36} | EmpID={str(m.empresa_id or '-'):<36} | CPF={m.cpf or '-':<11} | Email={m.email or '-':<28} | Nome: {nome_exibir}")

        print("=" * 80 + "\n")
    finally:
        session1.close()
        session2.close()
    return 0


def cmd_audit(args):
    """Exibe os últimos registros do log de auditoria do RPA."""
    session2 = db_manager.get_db2_session()
    session1 = db_manager.get_db1_session()
    try:
        limit = args.limit or 20
        logs = []
        try:
            logs = session2.query(RPASyncLog).order_by(RPASyncLog.id.desc()).limit(limit).all()
        except Exception:
            try:
                logs = session1.query(RPASyncLog).order_by(RPASyncLog.id.desc()).limit(limit).all()
            except Exception:
                pass

        print("\n" + "=" * 90)
        print(f"                   LOGS DE AUDITORIA DO RPA (Últimos {len(logs)} registros)")
        print("=" * 90)
        for log in logs:
            print(
                f"[{log.synced_at.strftime('%Y-%m-%d %H:%M:%S')}] "
                f"{log.source_db.upper()} ➔ {log.target_db.upper()} | "
                f"{log.entity_type.upper():<9} | "
                f"Ação: {log.action:<7} | "
                f"Chave: {log.natural_key:<20} | "
                f"OrigemID: {log.source_id:<4} ➔ DestinoID: {log.target_id or '-':<4}"
            )
        print("=" * 90 + "\n")
    finally:
        session2.close()
        session1.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="efficientia-rpa",
        description="RPA de Sincronização Bidirecional entre Banco 1 (DB1 (Operacional) - Efficientia.sql) e Banco 2 (DB2 (Corporativo) - Efficientia-database).",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Comandos disponíveis")

    # run
    p_run = subparsers.add_parser("run", help="Executa um ciclo único de sincronização")
    p_run.add_argument("--dry-run", action="store_true", help="Simula alterações sem gravar no banco")

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="Executa o RPA em loop contínuo")
    p_daemon.add_argument("--interval", type=int, default=settings.sync_interval_seconds, help="Intervalo em segundos entre ciclos")
    p_daemon.add_argument("--dry-run", action="store_true", help="Simula alterações sem gravar no banco")

    # init-db
    p_init = subparsers.add_parser("init-db", help="Inicializa tabelas em ambos os bancos")
    p_init.add_argument("--seed", action="store_true", default=True, help="Popula dados iniciais de exemplo")

    # stats
    p_stats = subparsers.add_parser("stats", help="Exibe estatísticas e registros dos dois bancos")

    # audit
    p_audit = subparsers.add_parser("audit", help="Exibe histórico de auditoria do RPA")
    p_audit.add_argument("--limit", type=int, default=20, help="Quantidade máxima de logs a exibir")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    handlers = {
        "run": cmd_run,
        "daemon": cmd_daemon,
        "init-db": cmd_init_db,
        "stats": cmd_stats,
        "audit": cmd_audit,
    }

    handler = handlers.get(args.subcommand)
    if handler:
        sys.exit(handler(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
