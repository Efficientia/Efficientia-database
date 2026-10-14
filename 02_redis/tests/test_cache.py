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
    from src.cache.rate_limit import RateLimiter
    from src.cache.configuracao import ConfiguracaoCacheService
    from src import keys
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


class TestCacheAndRateLimit(unittest.TestCase):
    def setUp(self):
        if not HAS_DEPS:
            self.skipTest("redis ou fakeredis não instalado neste ambiente")
        self.fake_r = fakeredis.FakeRedis(decode_responses=True)
        self.limiter = RateLimiter(redis_client=self.fake_r)
        self.cache_service = ConfiguracaoCacheService(redis_client=self.fake_r)

    def test_rate_limiter_bloqueio_apos_exceder(self):
        user_id = str(uuid.uuid4())
        max_allowed = 3

        # 3 chamadas devem ser aceitas
        for i in range(max_allowed):
            permitido, count = self.limiter.verificar_limite(user_id, max_requisicoes=max_allowed, janela_segundos=10)
            self.assertTrue(permitido)
            self.assertEqual(count, i + 1)

        # 4ª chamada deve ser rejeitada
        permitido, count = self.limiter.verificar_limite(user_id, max_requisicoes=max_allowed, janela_segundos=10)
        self.assertFalse(permitido)
        self.assertEqual(count, 4)

    def test_cache_hit_and_invalidation(self):
        empresa_id = str(uuid.uuid4())
        cache_key = keys.cache_config(empresa_id)

        # Preenche o cache simulando entrada prévia
        dummy_config = {
            "empresa_id": empresa_id,
            "tempo_max_viagem_horas": 8,
            "mortalidade_bloqueio_cabecas": 1,
            "meta_mortalidade": 0.5,
        }
        self.fake_r.set(cache_key, json.dumps(dummy_config))

        # Deve dar Cache-HIT
        data = self.cache_service.get_configuracao(empresa_id)
        self.assertIsNotNone(data)
        self.assertEqual(data["tempo_max_viagem_horas"], 8)

        # Invalidação
        self.cache_service.invalidar(empresa_id)
        self.assertIsNone(self.fake_r.get(cache_key))


if __name__ == "__main__":
    unittest.main()
