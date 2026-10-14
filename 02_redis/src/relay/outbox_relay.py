"""Transactional Outbox Relay.

Lê eventos pendentes da tabela sc_operacao.tb_outbox_evento no PostgreSQL com
bloqueio não-bloqueante (FOR UPDATE SKIP LOCKED) e os encaminha de forma confiável
para os Redis Streams da respectiva empresa no Upstash.
"""

import json
import logging
import time
from typing import Optional
import redis
import psycopg

from ..config import settings
from ..connection import get_db_connection, get_redis_client
from .. import keys

logger = logging.getLogger("efficientia.relay")


class OutboxRelay:
    """Serviço de publicação assíncrona do banco relacional para o Redis."""

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        db_conn: Optional[psycopg.Connection] = None,
    ):
        self.redis = redis_client or get_redis_client()
        self.db_conn = db_conn
        self._running = True

    def process_batch(self, batch_size: Optional[int] = None) -> int:
        """Processa um lote de eventos pendentes da Outbox. Retorna o total processado."""
        limit = batch_size or settings.relay_batch_size
        should_close_conn = False

        conn = self.db_conn
        if conn is None or conn.closed:
            conn = get_db_connection()
            should_close_conn = True

        processed_count = 0
        try:
            with conn.cursor() as cur:
                # 1. Busca eventos com SKIP LOCKED para permitir múltiplos relays concorrentes
                cur.execute(
                    """
                    SELECT id, empresa_id, tipo_evento, agregado_tipo, agregado_id, payload, criado_em
                    FROM sc_operacao.tb_outbox_evento
                    WHERE processado_em IS NULL AND erro_tentativas < %s
                    ORDER BY criado_em ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED;
                    """,
                    (settings.max_job_retries, limit),
                )
                events = cur.fetchall()

                if not events:
                    return 0

                logger.info("Processando lote de %d evento(s) da Outbox...", len(events))

                for ev in events:
                    event_id = ev["id"]
                    empresa_id = str(ev["empresa_id"])
                    stream_key = keys.stream_eventos(empresa_id)

                    stream_data = {
                        "outbox_id": str(event_id),
                        "empresa_id": empresa_id,
                        "tipo_evento": ev["tipo_evento"],
                        "agregado_tipo": ev["agregado_tipo"],
                        "agregado_id": str(ev["agregado_id"]),
                        "payload": json.dumps(ev["payload"], ensure_ascii=False),
                        "criado_em": ev["criado_em"].isoformat(),
                    }

                    try:
                        # 2. Publica no Redis Stream (XADD)
                        msg_id = self.redis.xadd(stream_key, stream_data)

                        # 3. Marca como processado no PostgreSQL
                        cur.execute(
                            """
                            UPDATE sc_operacao.tb_outbox_evento
                            SET processado_em = CURRENT_TIMESTAMP,
                                ultimo_erro = NULL
                            WHERE id = %s;
                            """,
                            (event_id,),
                        )
                        processed_count += 1
                        logger.debug("Evento %s publicado no stream %s (msg: %s)", event_id, stream_key, msg_id)

                    except Exception as err:
                        error_msg = str(err)[:1000]
                        logger.error("Erro ao enviar evento %s para o Redis: %s", event_id, error_msg)
                        cur.execute(
                            """
                            UPDATE sc_operacao.tb_outbox_evento
                            SET erro_tentativas = erro_tentativas + 1,
                                ultimo_erro = %s
                            WHERE id = %s;
                            """,
                            (error_msg, event_id),
                        )

                # Commit transacional no PostgreSQL garantindo efetivação dos status
                conn.commit()

        except Exception as batch_err:
            logger.error("Erro inesperado no lote do relay: %s", batch_err)
            if conn and not conn.closed:
                conn.rollback()
        finally:
            if should_close_conn and conn and not conn.closed:
                conn.close()

        return processed_count

    def run_forever(self) -> None:
        """Loop contínuo de encaminhamento da Outbox."""
        logger.info("Outbox Relay iniciado (intervalo de polling: %.1fs)...", settings.relay_poll_interval)
        while self._running:
            try:
                count = self.process_batch()
                if count == 0:
                    time.sleep(settings.relay_poll_interval)
            except KeyboardInterrupt:
                logger.info("Outbox Relay interrompido pelo usuário.")
                break
            except Exception as e:
                logger.error("Erro no loop do Outbox Relay: %s", e)
                time.sleep(settings.relay_poll_interval)

    def stop(self) -> None:
        """Para a execução do loop."""
        self._running = False
