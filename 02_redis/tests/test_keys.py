import sys
from pathlib import Path
import unittest
import uuid

# Garante que a pasta 02_redis está no PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import keys


class TestKeys(unittest.TestCase):
    def test_stream_eventos_key_format(self):
        empresa_id = str(uuid.uuid4())
        key = keys.stream_eventos(empresa_id)
        self.assertTrue(key.startswith("efficientia:"))
        self.assertIn(f":{empresa_id}:stream:eventos", key)

    def test_stream_dlq_key_format(self):
        empresa_id = str(uuid.uuid4())
        key = keys.stream_dlq(empresa_id)
        self.assertIn(f":{empresa_id}:stream:dlq", key)

    def test_lock_key_format(self):
        empresa_id = str(uuid.uuid4())
        key = keys.lock_job(empresa_id, "relatorio_123")
        self.assertIn(f":{empresa_id}:lock:relatorio_123", key)


if __name__ == "__main__":
    unittest.main()
