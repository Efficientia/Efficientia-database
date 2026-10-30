"""Job de detecção e disparo de alerta crítico de mortalidade animal."""

import json
import logging
from typing import Any, Dict
from .base import BaseJob

logger = logging.getLogger("efficientia.jobs.mortalidade")


class AlertaMortalidadeJob(BaseJob):
    """Monitora viagens e dispara alertas para casos de morte no transporte pecuário."""

    def can_handle(self, tipo_evento: str) -> bool:
        return tipo_evento in ("relatorio.status_alterado", "relatorio.criado")

    def process(self, event_data: Dict[str, Any]) -> bool:
        payload_raw = event_data.get("payload", "{}")
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw

        relatorio_id = payload.get("relatorio_id")
        empresa_id = payload.get("empresa_id")
        qtd_morto = int(payload.get("qtd_morto", 0))
        total_embarcados = int(payload.get("total_embarcados", 0))
        status_novo = payload.get("status_novo")

        # Só processa relatórios submetidos ou aprovados
        if status_novo not in ("pendente", "aprovado"):
            return True

        if qtd_morto > 0:
            taxa = (qtd_morto / total_embarcados * 100) if total_embarcados > 0 else 0.0
            logger.warning(
                "[ALERTA DE MORTALIDADE] Relatório %s (Empresa %s): %d óbito(s) de animal registrado(s)! "
                "Taxa de mortalidade na viagem: %.2f%%. Ação requerida: retenção para laudo veterinário SIF.",
                relatorio_id,
                empresa_id,
                qtd_morto,
                taxa,
            )
        else:
            logger.info("[INFO] Relatório %s com 100%% de sobrevivência animal (0 mortes).", relatorio_id)

        return True
