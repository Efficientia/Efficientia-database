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
    from src.ranking.leaderboard import LeaderboardService
    from src.jobs.atualizar_ranking import AtualizarRankingJob
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False


class TestRanking(unittest.TestCase):
    def setUp(self):
        if not HAS_DEPS:
            self.skipTest("redis ou fakeredis não instalado neste ambiente")
        self.fake_r = fakeredis.FakeRedis(decode_responses=True)
        self.empresa_id = str(uuid.uuid4())
        self.leaderboard = LeaderboardService(redis_client=self.fake_r)

    def test_registrar_viagem_e_consultar_volume(self):
        m1 = str(uuid.uuid4())
        m2 = str(uuid.uuid4())
        ano_mes = "2026-10"

        # Motorista 1 transporta 100 animais
        self.leaderboard.registrar_viagem_finalizada(
            self.empresa_id, m1, data_referencia="2026-10-01", total_embarcados=100, qtd_morto=1
        )
        # Motorista 2 transporta 250 animais
        self.leaderboard.registrar_viagem_finalizada(
            self.empresa_id, m2, data_referencia="2026-10-02", total_embarcados=250, qtd_morto=0
        )

        top_volume = self.leaderboard.get_top_volume(self.empresa_id, ano_mes, limit=2)
        self.assertEqual(len(top_volume), 2)
        # Motorista 2 deve ser o primeiro colocado por volume
        self.assertEqual(top_volume[0]["motorista_id"], m2)
        self.assertEqual(top_volume[0]["total_cabecas"], 250)
        self.assertEqual(top_volume[1]["motorista_id"], m1)

    def test_ranking_mortalidade_calculo_taxa(self):
        m1 = str(uuid.uuid4())
        m2 = str(uuid.uuid4())
        ano_mes = "2026-10"

        # M1: 2 mortes em 100 animais = 2.0%
        self.leaderboard.registrar_viagem_finalizada(
            self.empresa_id, m1, data_referencia="2026-10-01", total_embarcados=100, qtd_morto=2
        )
        # M2: 0 mortes em 100 animais = 0.0%
        self.leaderboard.registrar_viagem_finalizada(
            self.empresa_id, m2, data_referencia="2026-10-02", total_embarcados=100, qtd_morto=0
        )

        # Menor mortalidade primeiro: M2 deve ser #1
        top_mortalidade = self.leaderboard.get_top_mortalidade(
            self.empresa_id, ano_mes, limit=2, menor_mortalidade_primeiro=True
        )
        self.assertEqual(top_mortalidade[0]["motorista_id"], m2)
        self.assertEqual(top_mortalidade[0]["taxa_mortalidade_pct"], 0.0)
        self.assertEqual(top_mortalidade[1]["motorista_id"], m1)
        self.assertEqual(top_mortalidade[1]["taxa_mortalidade_pct"], 2.0)

    def test_atualizar_ranking_job_via_evento(self):
        job = AtualizarRankingJob(redis_client=self.fake_r)
        self.assertTrue(job.can_handle("relatorio.status_alterado"))
        self.assertFalse(job.can_handle("relatorio.criado"))

        m_id = str(uuid.uuid4())
        payload = {
            "empresa_id": self.empresa_id,
            "motorista_id": m_id,
            "status_novo": "aprovado",
            "total_embarcados": 50,
            "qtd_morto": 1,
            "data_chegada_unidade": "2026-10-14",
        }

        ok = job.process({"payload": json.dumps(payload), "tipo_evento": "relatorio.status_alterado"})
        self.assertTrue(ok)

        pos = self.leaderboard.get_posicao_motorista(self.empresa_id, "2026-10", m_id)
        self.assertEqual(pos["total_cabecas"], 50)
        self.assertEqual(pos["taxa_mortalidade"], 2.0)


if __name__ == "__main__":
    unittest.main()
