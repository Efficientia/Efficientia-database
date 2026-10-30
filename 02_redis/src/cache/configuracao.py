"""Cache de parametrizações operacionais corporativas no Redis.

Reduz a latência de consultas recorrentes a sc_corporativo.tb_configuracao_operacao
(como tempo máximo de viagem, bloqueio por mortes e SLAs) de ~40ms no banco relacional
para <2ms no Redis em memória.
"""

import json
import logging
from typing import Any, Dict, Optional
import psycopg
import redis

from ..connection import get_db_connection, get_redis_client
from .. import keys

logger = logging.getLogger("efficientia.cache.config")

DEFAULT_CACHE_TTL_SECONDS = 3600  # 1 hora


class ConfiguracaoCacheService:
    """Gerenciador de cache com estratégia Cache-Aside para parâmetros da empresa."""

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        db_conn: Optional[psycopg.Connection] = None,
    ):
        self.redis = redis_client or get_redis_client()
        self.db_conn = db_conn

    def get_configuracao(self, empresa_id: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Recupera as configurações com fallback automático para o PostgreSQL."""
        cache_key = keys.cache_config(empresa_id)

        # 1. Tenta recuperar do Redis (Cache-Hit)
        if not force_refresh:
            cached_data = self.redis.get(cache_key)
            if cached_data:
                logger.debug("Cache-HIT para configurações da empresa %s", empresa_id)
                return json.loads(cached_data)

        # 2. Em caso de Cache-Miss, busca no banco relacional
        logger.info("Cache-MISS para configurações da empresa %s. Consultando PostgreSQL...", empresa_id)
        should_close = False
        conn = self.db_conn
        if conn is None or conn.closed:
            conn = get_db_connection()
            should_close = True

        config_data = None
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        empresa_id,
                        tempo_max_viagem_horas,
                        mortalidade_bloqueio_cabecas,
                        prazo_analise_horas,
                        meta_mortalidade,
                        qtd_assinaturas_obrigatorias,
                        alerta_sirene_re,
                        alerta_inspecao_dias,
                        alerta_cnh_vencida,
                        alerta_tempo_parada_imprevista
                    FROM sc_corporativo.tb_configuracao_operacao
                    WHERE empresa_id = %s;
                    """,
                    (empresa_id,),
                )
                row = cur.fetchone()
                if row:
                    config_data = dict(row)
                    # Converte UUID e Decimais para JSON serializável
                    config_data["empresa_id"] = str(config_data["empresa_id"])
                    config_data["meta_mortalidade"] = float(config_data["meta_mortalidade"])

                    # 3. Salva no Redis com TTL
                    self.redis.setex(
                        cache_key,
                        DEFAULT_CACHE_TTL_SECONDS,
                        json.dumps(config_data),
                    )
        finally:
            if should_close and conn and not conn.closed:
                conn.close()

        return config_data

    def invalidar(self, empresa_id: str) -> bool:
        """Invalida a entrada de cache da empresa."""
        cache_key = keys.cache_config(empresa_id)
        deleted = self.redis.delete(cache_key)
        logger.info("Cache invalidado para empresa %s (deletado: %s)", empresa_id, bool(deleted))
        return bool(deleted)
