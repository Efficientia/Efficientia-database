"""CLI de execução dos serviços Redis do Efficientia."""

import argparse
import json
import logging
import sys
import uuid

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


def cmd_test_event(empresa_id: str, qtd_morto: int, qtd_emergencia: int):
    """Envia um evento simulado diretamente para o Redis Stream da empresa."""
    from src.connection import get_redis_client
    from src import keys

    r = get_redis_client()
    stream_key = keys.stream_eventos(empresa_id)
    payload = {
        "relatorio_id": str(uuid.uuid4()),
        "empresa_id": empresa_id,
        "status_novo": "aprovado",
        "qtd_morto": qtd_morto,
        "qtd_emergencia": qtd_emergencia,
        "total_embarcados": 50,
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


def main():
    parser = argparse.ArgumentParser(description="Efficientia - Serviços Redis")
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
    test_parser.add_argument("--morto", type=int, default=1, help="Quantidade de mortos simulados")
    test_parser.add_argument("--emergencia", type=int, default=0, help="Quantidade de emergências")

    args = parser.parse_args()

    if args.command == "check":
        cmd_check()
    elif args.command == "relay":
        cmd_relay()
    elif args.command == "worker":
        cmd_worker(args.empresa)
    elif args.command == "test-event":
        cmd_test_event(args.empresa, args.morto, args.emergencia)


if __name__ == "__main__":
    main()
