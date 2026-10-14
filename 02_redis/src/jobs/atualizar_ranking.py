"""Job de fila para atualização dos rankings em tempo real após aprovação de viagem."""

import json
import logging
from typing import Any, Dict, Optional
import redis

from .base import BaseJob
from ..ranking.leaderboard import LeaderboardService

logger = logging.getLogger("efficientia.jobs.ranking")


class AtualizarRankingJob(BaseJob):
    """Atualiza placares de volume e mortalidade no Redis quando a viagem é aprovada."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.leaderboard = LeaderboardService(redis_client=redis_client)

    def can_handle(self, tipo_evento: str) -> bool:
        return tipo_evento == "relatorio.status_alterado"

    def process(self, event_data: Dict[str, Any]) -> bool:
        payload_raw = event_data.get("payload", "{}")
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw

        status_novo = payload.get("status_novo")
        if status_novo != "aprovado":
            return True

        empresa_id = str(payload.get("empresa_id", ""))
        motorista_id = str(payload.get("motorista_id", ""))
        data_chegada = payload.get("data_chegada_unidade")
        total_embarcados = int(payload.get("total_embarcados", 0))
        qtd_morto = int(payload.get("qtd_morto", 0))

        if not empresa_id or not motorista_id:
            logger.error("Dados insuficientes no evento para atualizar ranking: %s", payload)
            return False

        stats = self.leaderboard.registrar_viagem_finalizada(
            empresa_id=empresa_id,
            motorista_id=motorista_id,
            data_referencia=data_chegada,
            total_embarcados=total_embarcados,
            qtd_morto=qtd_morto,
        )

        logger.info(
            "Placar atualizado para motorista %s: %d cabeças acumuladas (mortalidade: %.2f%%).",
            motorista_id,
            stats["total_embarcados"],
            stats["taxa_mortalidade"],
        )
        return True
