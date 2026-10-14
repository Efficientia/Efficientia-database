"""CLI de execução dos serviços Redis do Efficientia."""

import argparse
from datetime import datetime
import json
import logging
from pathlib import Path
import sys
import uuid

# Garante que o diretório 02_redis esteja no PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("efficientia.main")


def cmd_check():
    """Testa conexões com o PostgreSQL e Upstash Redis."""
    from src.connection import test_connections
    logger.info("Testando conectividade dos bancos de dados...")
    results = test_connections()

    print("\n--- STATUS DAS CONEXÕES ---")
    print(f"Redis (Upstash):    {'[OK] CONECTADO' if results['redis'] else '[FALHA] Não conectado'}")
    print(f"PostgreSQL (Supabase): {'[OK] CONECTADO' if results['postgres'] else '[FALHA] Não conectado'}")
    print("---------------------------\n")

    if not all(results.values()):
        sys.exit(1)


def cmd_relay():
    """Inicia o Outbox Relay para transferir eventos do PostgreSQL para o Redis."""
    from src.relay.outbox_relay import OutboxRelay
    relay = OutboxRelay()
    relay.run_forever()


def cmd_worker(empresa_id: str):
    """Inicia o worker de consumo de filas para uma empresa."""
    from src.queues.consumer import StreamConsumer
    consumer = StreamConsumer(empresa_id=empresa_id)
    consumer.run_forever()


def cmd_test_event(empresa_id: str, motorista_id: str, qtd_morto: int, qtd_emergencia: int):
    """Envia um evento simulado diretamente para o Redis Stream da empresa."""
    from src.connection import get_redis_client
    from src import keys

    r = get_redis_client()
    stream_key = keys.stream_eventos(empresa_id)
    payload = {
        "relatorio_id": str(uuid.uuid4()),
        "empresa_id": empresa_id,
        "motorista_id": motorista_id,
        "status_novo": "aprovado",
        "qtd_morto": qtd_morto,
        "qtd_emergencia": qtd_emergencia,
        "total_embarcados": 50,
        "data_chegada_unidade": datetime.utcnow().isoformat(),
    }

    event = {
        "outbox_id": str(uuid.uuid4()),
        "empresa_id": empresa_id,
        "tipo_evento": "relatorio.status_alterado",
        "agregado_tipo": "relatorio_viagem",
        "agregado_id": payload["relatorio_id"],
        "payload": json.dumps(payload),
    }

    msg_id = r.xadd(stream_key, event)
    logger.info("Evento simulado publicado com sucesso no Stream '%s' (ID: %s)", stream_key, msg_id)


def cmd_ranking(empresa_id: str, ano_mes: str):
    """Exibe os rankings em tempo real armazenados no Redis Sorted Sets."""
    from src.ranking.leaderboard import LeaderboardService
    leaderboard = LeaderboardService()

    periodo = ano_mes or datetime.utcnow().strftime("%Y-%m")

    print(f"\n=======================================================")
    print(f"📊 LEADERBOARDS EM TEMPO REAL - PERÍODO: {periodo}")
    print(f"Empresa: {empresa_id}")
    print(f"=======================================================\n")

    # 1. Top Volume
    top_volume = leaderboard.get_top_volume(empresa_id, periodo, limit=5)
    print("🏆 TOP 5 MOTORISTAS POR VOLUME TRANSPORTADO (Cabeças):")
    if not top_volume:
        print("  (Nenhum dado registrado para este período)")
    for item in top_volume:
        print(f"  #{item['posicao']} - Motorista: {item['motorista_id']} | Total: {item['total_cabecas']} animais")

    print("\n-------------------------------------------------------")
    # 2. Menor Mortalidade
    top_mortalidade = leaderboard.get_top_mortalidade(empresa_id, periodo, limit=5, menor_mortalidade_primeiro=True)
    print("🌿 TOP 5 MOTORISTAS COM MENOR ÍNDICE DE MORTALIDADE:")
    if not top_mortalidade:
        print("  (Nenhum dado registrado para este período)")
    for item in top_mortalidade:
        print(f"  #{item['posicao']} - Motorista: {item['motorista_id']} | Taxa: {item['taxa_mortalidade_pct']:.2f}%")
    print(f"=======================================================\n")


def cmd_reconcile(empresa_id: str, ano_mes: str):
    """Reconcilia e reconstrói o ranking no Redis a partir da Materialized View do PostgreSQL."""
    from src.ranking.reconciliacao import RankingReconciler
    reconciler = RankingReconciler()
    logger.info("Iniciando reconciliação analítica para a empresa %s...", empresa_id)
    total = reconciler.reconciliar_empresa(empresa_id, ano_mes)
    print(f"\n[OK] Reconciliação concluída: {total} motorista(s) sincronizados do PostgreSQL para o Redis.\n")


def cmd_cache_config(empresa_id: str, force_refresh: bool):
    """Demonstra o uso de Cache-Aside para parâmetros operacionais."""
    from src.cache.configuracao import ConfiguracaoCacheService
    service = ConfiguracaoCacheService()
    config = service.get_configuracao(empresa_id, force_refresh=force_refresh)
    print("\n--- CONFIGURAÇÃO OPERACIONAL DA EMPRESA ---")
    if config:
        print(json.dumps(config, indent=2, ensure_ascii=False))
    else:
        print("Empresa não encontrada.")
    print("-------------------------------------------\n")


def main():
    parser = argparse.ArgumentParser(description="Efficientia - Serviços Redis (Filas e Rankings)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcomando check
    subparsers.add_parser("check", help="Testa conexões com Upstash e Supabase")

    # Subcomando relay
    subparsers.add_parser("relay", help="Inicia o Transactional Outbox Relay")

    # Subcomando worker
    worker_parser = subparsers.add_parser("worker", help="Inicia o Worker de Filas")
    worker_parser.add_argument("--empresa", required=True, help="UUID da empresa")

    # Subcomando test-event
    test_parser = subparsers.add_parser("test-event", help="Dispara um evento de teste na fila")
    test_parser.add_argument("--empresa", required=True, help="UUID da empresa")
    test_parser.add_argument("--motorista", default=str(uuid.uuid4()), help="UUID do motorista simulado")
    test_parser.add_argument("--morto", type=int, default=1, help="Quantidade de mortos simulados")
    test_parser.add_argument("--emergencia", type=int, default=0, help="Quantidade de emergências")

    # Subcomando ranking
    rank_parser = subparsers.add_parser("ranking", help="Consulta o Leaderboard em tempo real")
    rank_parser.add_argument("--empresa", required=True, help="UUID da empresa")
    rank_parser.add_argument("--mes", default=None, help="Mês de referência (AAAA-MM). Padrão: mês atual")

    # Subcomando reconcile
    rec_parser = subparsers.add_parser("reconcile", help="Reconstrói o ranking no Redis a partir do PostgreSQL")
    rec_parser.add_argument("--empresa", required=True, help="UUID da empresa")
    rec_parser.add_argument("--mes", default=None, help="Mês de referência (AAAA-MM)")

    # Subcomando cache-config
    cache_parser = subparsers.add_parser("cache-config", help="Consulta configuração com Cache-Aside")
    cache_parser.add_argument("--empresa", required=True, help="UUID da empresa")
    cache_parser.add_argument("--refresh", action="store_true", help="Força atualização ignorando cache")

    args = parser.parse_args()

    if args.command == "check":
        cmd_check()
    elif args.command == "relay":
        cmd_relay()
    elif args.command == "worker":
        cmd_worker(args.empresa)
    elif args.command == "test-event":
        cmd_test_event(args.empresa, args.motorista, args.morto, args.emergencia)
    elif args.command == "ranking":
        cmd_ranking(args.empresa, args.mes)
    elif args.command == "reconcile":
        cmd_reconcile(args.empresa, args.mes)
    elif args.command == "cache-config":
        cmd_cache_config(args.empresa, args.refresh)


if __name__ == "__main__":
    main()
