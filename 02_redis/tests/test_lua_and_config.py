"""Validação de integridade sintática e funcional dos artefatos de configuração e scripts Lua do Redis."""

import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import fakeredis
    import redis
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


class TestRedisConfigAndLua(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.config_path = self.base_dir / "config" / "redis.conf"
        self.lua_dir = self.base_dir / "scripts"
        self.script_ranking_path = self.lua_dir / "registrar_viagem_ranking.lua"
        self.script_ratelimit_path = self.lua_dir / "verificar_rate_limit.lua"

    def test_arquivo_redis_conf_existe_e_contem_diretivas_criticas(self):
        self.assertTrue(self.config_path.exists(), "redis.conf deve existir na pasta config/")
        conteudo = self.config_path.read_text(encoding="utf-8")

        self.assertIn("maxmemory-policy noeviction", conteudo)
        self.assertIn("appendonly yes", conteudo)
        self.assertIn("port 6379", conteudo)
        self.assertIn("databases 16", conteudo)

    def test_scripts_lua_existem_e_possuem_conteudo(self):
        self.assertTrue(self.script_ranking_path.exists(), "Script registrar_viagem_ranking.lua deve existir")
        self.assertTrue(self.script_ratelimit_path.exists(), "Script verificar_rate_limit.lua deve existir")

        lua_ranking = self.script_ranking_path.read_text(encoding="utf-8")
        lua_ratelimit = self.script_ratelimit_path.read_text(encoding="utf-8")

        self.assertIn("HINCRBY", lua_ranking)
        self.assertIn("ZINCRBY", lua_ranking)
        self.assertIn("ZADD", lua_ranking)

        self.assertIn("INCR", lua_ratelimit)
        self.assertIn("EXPIRE", lua_ratelimit)
        self.assertIn("TTL", lua_ratelimit)

    def test_execucao_script_rate_limit_em_fakeredis(self):
        if not HAS_DEPS:
            self.skipTest("fakeredis não instalado neste ambiente")

        fake_r = fakeredis.FakeRedis(decode_responses=True)
        lua_ratelimit = self.script_ratelimit_path.read_text(encoding="utf-8")

        key = "efficientia:test:ratelimit:usuario_123:viagens"
        cmd = fake_r.register_script(lua_ratelimit)

        # Chamada 1: permitida (1/3)
        res1 = cmd(keys=[key], args=[3, 60])
        self.assertEqual(res1[0], 1)
        self.assertEqual(res1[1], 1)
        self.assertEqual(res1[2], 2)

        # Chamada 2: permitida (2/3)
        res2 = cmd(keys=[key], args=[3, 60])
        self.assertEqual(res2[0], 2)
        self.assertEqual(res2[1], 1)
        self.assertEqual(res2[2], 1)

        # Chamada 3: permitida (3/3)
        res3 = cmd(keys=[key], args=[3, 60])
        self.assertEqual(res3[0], 3)
        self.assertEqual(res3[1], 1)
        self.assertEqual(res3[2], 0)

        # Chamada 4: bloqueada (4/3)
        res4 = cmd(keys=[key], args=[3, 60])
        self.assertEqual(res4[0], 4)
        self.assertEqual(res4[1], 0)
        self.assertEqual(res4[2], 0)


if __name__ == "__main__":
    unittest.main()
