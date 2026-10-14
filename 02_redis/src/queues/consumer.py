"""Consumidor de Filas com Redis Streams e Consumer Groups.

Garante entrega confiável (At-least-once), confirmação explícita de mensagens (XACK),
bloqueio com timeout (XREADGROUP com BLOCK) para economia de quota no Upstash,
e envio para Dead Letter Queue (DLQ) em caso de falhas consecutivas.
"""

import json
import logging
import socket
from typing import List, Optional
import redis
from redis.exceptions import ResponseError

from ..config import settings
from ..connection import get_redis_client
from .. import keys
from ..jobs.base import BaseJob
from ..jobs.alerta_mortalidade import AlertaMortalidadeJob
from ..jobs.alerta_sla import AlertaEmergenciaJob
from ..jobs.atualizar_ranking import AtualizarRankingJob

logger = logging.getLogger("efficientia.consumer")


class StreamConsumer:
    """Consumidor de mensagens assíncronas do Redis Streams."""

    def __init__(
        self,
        empresa_id: str,
        consumer_name: Optional[str] = None,
        redis_client: Optional[redis.Redis] = None,
        jobs: Optional[List[BaseJob]] = None,
    ):
        self.empresa_id = empresa_id
        self.redis = redis_client or get_redis_client()
        self.group_name = keys.CONSUMER_GROUP_NAME
        self.consumer_name = consumer_name or f"worker_{socket.gethostname()}"
        self.stream_key = keys.stream_eventos(empresa_id)
        self.dlq_key = keys.stream_dlq(empresa_id)
        self.jobs = jobs or [
            AlertaMortalidadeJob(),
            AlertaEmergenciaJob(),
            AtualizarRankingJob(redis_client=self.redis),
        ]
        self._running = True

    def ensure_group(self) -> None:
        """Cria o Consumer Group na Stream de forma idempotente."""
        try:
            self.redis.xgroup_create(
                name=self.stream_key,
                groupname=self.group_name,
                id="0",
                mkstream=True,
            )
            logger.info("Consumer Group '%s' criado na stream '%s'.", self.group_name, self.stream_key)
        except ResponseError as e:
            if "BUSYGROUP" in str(e):
                logger.debug("Consumer Group '%s' já existe na stream '%s'.", self.group_name, self.stream_key)
            else:
                raise

    def process_messages(self, count: int = 10) -> int:
        """Lê e processa um lote de mensagens pendentes do Consumer Group."""
        self.ensure_group()

        # Leitura bloqueante (BLOCK) para evitar requisições contínuas ao Upstash
        response = self.redis.xreadgroup(
            groupname=self.group_name,
            consumername=self.consumer_name,
            streams={self.stream_key: ">"},
            count=count,
            block=settings.worker_block_ms,
        )

        if not response:
            return 0

        total_processed = 0
        for stream, messages in response:
            for message_id, data in messages:
                success = self._handle_single_message(message_id, data)
                if success:
                    # Confirma o processamento com XACK
                    self.redis.xack(self.stream_key, self.group_name, message_id)
                    total_processed += 1
                else:
                    logger.error("Falha ao processar mensagem %s. Encaminhando para DLQ...", message_id)
                    self._send_to_dlq(message_id, data)
                    self.redis.xack(self.stream_key, self.group_name, message_id)

        return total_processed

    def _handle_single_message(self, message_id: str, data: dict) -> bool:
        """Dispara os jobs registrados para o evento recebido."""
        tipo_evento = data.get("tipo_evento", "")
        logger.info("Recebida mensagem %s [Tipo: %s]", message_id, tipo_evento)

        all_ok = True
        for job in self.jobs:
            if job.can_handle(tipo_evento):
                try:
                    job_success = job.process(data)
                    if not job_success:
                        all_ok = False
                except Exception as err:
                    logger.error("Exceção no job %s ao processar mensagem %s: %s", job.__class__.__name__, message_id, err)
                    all_ok = False

        return all_ok

    def _send_to_dlq(self, message_id: str, data: dict) -> None:
        """Move mensagem não processável para a Dead Letter Queue para auditoria posterior."""
        dlq_data = dict(data)
        dlq_data["original_id"] = message_id
        dlq_data["failed_at_group"] = self.group_name
        self.redis.xadd(self.dlq_key, dlq_data)

    def run_forever(self) -> None:
        """Executa o loop contínuo de consumo da fila."""
        logger.info(
            "Worker '%s' iniciado para a empresa %s (Stream: %s, Grupo: %s)...",
            self.consumer_name,
            self.empresa_id,
            self.stream_key,
            self.group_name,
        )
        while self._running:
            try:
                self.process_messages()
            except KeyboardInterrupt:
                logger.info("Worker interrompido pelo usuário.")
                break
            except Exception as e:
                logger.error("Erro no loop do Worker: %s", e)

    def stop(self) -> None:
        self._running = False
