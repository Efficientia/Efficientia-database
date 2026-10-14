"""Job de monitoramento de emergência veterinária e SLA operacional."""

import json
import logging
from typing import Any, Dict
from .base import BaseJob

logger = logging.getLogger("efficientia.jobs.sla")


class AlertaEmergenciaJob(BaseJob):
    """Monitora animais fadigados/acidentados que exigem abate de emergência no frigorífico."""

    def can_handle(self, tipo_evento: str) -> bool:
        return tipo_evento in ("relatorio.status_alterado", "relatorio.criado")

    def process(self, event_data: Dict[str, Any]) -> bool:
        payload_raw = event_data.get("payload", "{}")
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw

        relatorio_id = payload.get("relatorio_id")
        empresa_id = payload.get("empresa_id")
        qtd_emergencia = int(payload.get("qtd_emergencia", 0))

        if qtd_emergencia > 0:
            logger.warning(
                "⚠️ [ALERTA DE EMERGÊNCIA] Relatório %s (Empresa %s): %d cabeça(s) em estado de emergência! "
                "Prioridade máxima na recepção do curral do frigorífico para sangria imediata.",
                relatorio_id,
                empresa_id,
                qtd_emergencia,
            )

        return True
