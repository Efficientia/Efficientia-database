"""Controle de taxa de requisições (Rate Limiter) com Redis.

Previne abusos, disparos em loop por aplicativos desconectados ou ataques de negação
de serviço (DoS) em endpoints de sincronização de relatórios.
"""

import logging
from typing import Optional, Tuple
import redis

from ..connection import get_redis_client
from .. import keys

logger = logging.getLogger("efficientia.ratelimit")


class RateLimiter:
    """Implementa o algoritmo de Janela Fixa com INCR e EXPIRE atômicos."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client or get_redis_client()

    def verificar_limite(
        self,
        usuario_id: str,
        max_requisicoes: int = 20,
        janela_segundos: int = 60,
    ) -> Tuple[bool, int]:
        """Verifica se o usuário excedeu o limite de chamadas na janela de tempo.

        Retorna (permitido: bool, total_na_janela: int).
        """
        key = keys.rate_limit_report(usuario_id)

        pipe = self.redis.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        results = pipe.execute()

        contador = int(results[0])
        ttl = int(results[1])

        # Se a chave acabou de ser criada, define o tempo de expiração da janela
        if ttl == -1:
            self.redis.expire(key, janela_segundos)

        if contador > max_requisicoes:
            logger.warning(
                "🛑 [RATE LIMIT EXCEDIDO] Usuário %s atingiu %d requisições (limite: %d/%ds).",
                usuario_id,
                contador,
                max_requisicoes,
                janela_segundos,
            )
            return False, contador

        return True, contador
