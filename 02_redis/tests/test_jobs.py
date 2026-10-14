import json
import sys
from pathlib import Path
import unittest
import uuid

# Garante que a pasta 02_redis está no PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.jobs.alerta_mortalidade import AlertaMortalidadeJob
from src.jobs.alerta_sla import AlertaEmergenciaJob


class TestJobs(unittest.TestCase):
    def test_alerta_mortalidade_com_obito(self):
        job = AlertaMortalidadeJob()
        self.assertTrue(job.can_handle("relatorio.status_alterado"))
        self.assertFalse(job.can_handle("outro.evento"))

        payload = {
            "relatorio_id": str(uuid.uuid4()),
            "empresa_id": str(uuid.uuid4()),
            "status_novo": "aprovado",
            "qtd_morto": 2,
            "total_embarcados": 40,
        }

        event = {"payload": json.dumps(payload), "tipo_evento": "relatorio.status_alterado"}
        result = job.process(event)
        self.assertTrue(result)

    def test_alerta_mortalidade_sem_obito(self):
        job = AlertaMortalidadeJob()
        payload = {
            "relatorio_id": str(uuid.uuid4()),
            "empresa_id": str(uuid.uuid4()),
            "status_novo": "aprovado",
            "qtd_morto": 0,
            "total_embarcados": 50,
        }

        event = {"payload": payload, "tipo_evento": "relatorio.status_alterado"}
        result = job.process(event)
        self.assertTrue(result)

    def test_alerta_emergencia(self):
        job = AlertaEmergenciaJob()
        self.assertTrue(job.can_handle("relatorio.criado"))

        payload = {
            "relatorio_id": str(uuid.uuid4()),
            "empresa_id": str(uuid.uuid4()),
            "qtd_emergencia": 3,
        }

        event = {"payload": payload, "tipo_evento": "relatorio.criado"}
        result = job.process(event)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
