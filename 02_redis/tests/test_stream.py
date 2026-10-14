import json
import sys
from pathlib import Path
import unittest
import uuid

# Garante que a pasta 02_redis está no PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import redis
    import fakeredis
    from src.queues.consumer import StreamConsumer
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

from src import keys


class TestStreamConsumer(unittest.TestCase):
    def test_stream_consumer_workflow(self):
        if not HAS_DEPS:
            self.skipTest("redis ou fakeredis não instalado neste ambiente")

        fake_r = fakeredis.FakeRedis(decode_responses=True)
        empresa_id = str(uuid.uuid4())
        consumer = StreamConsumer(empresa_id=empresa_id, redis_client=fake_r)

        # 1. Cria grupo
        consumer.ensure_group()
        stream_key = keys.stream_eventos(empresa_id)

        # 2. Publica evento no stream
        event_payload = {
            "relatorio_id": str(uuid.uuid4()),
            "empresa_id": empresa_id,
            "status_novo": "aprovado",
            "qtd_morto": 1,
            "total_embarcados": 45,
        }
        fake_r.xadd(
            stream_key,
            {
                "tipo_evento": "relatorio.status_alterado",
                "payload": json.dumps(event_payload),
            },
        )

        # 3. Processa
        processed = consumer.process_messages(count=5)
        self.assertEqual(processed, 1)

        # 4. Verifica se mensagem foi confirmada com XACK
        pending = fake_r.xpending(stream_key, keys.CONSUMER_GROUP_NAME)
        self.assertEqual(pending["pending"], 0)


if __name__ == "__main__":
    unittest.main()
