"""Gerenciamento de conexões com Redis (Upstash) e PostgreSQL (Supabase)."""

import logging
from typing import Optional
import redis
import psycopg
from psycopg.rows import dict_row

from .config import settings

logger = logging.getLogger("efficientia.connection")

_redis_pool: Optional[redis.ConnectionPool] = None


def get_redis_client() -> redis.Redis:
    """Retorna cliente Redis conectado com pool reutilizável e suporte a TLS (rediss://)."""
    global _redis_pool
    if _redis_pool is None:
        logger.info("Inicializando pool de conexões com o Redis (%s)...", settings.app_env)
        _redis_pool = redis.ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_timeout=10,
            socket_connect_timeout=10,
            retry_on_timeout=True,
        )
    return redis.Redis(connection_pool=_redis_pool)


def get_db_connection() -> psycopg.Connection:
    """Retorna uma conexão ativa com o banco PostgreSQL / Supabase configurada com dict_row."""
    return psycopg.connect(
        settings.database_url,
        row_factory=dict_row,
        autocommit=False,
    )


def test_connections() -> dict[str, bool]:
    """Testa a conectividade com os dois bancos e retorna o status."""
    results = {"redis": False, "postgres": False}

    # Teste Redis
    try:
        r = get_redis_client()
        pong = r.ping()
        results["redis"] = (pong is True)
    except Exception as e:
        logger.error("Falha ao conectar no Redis: %s", e)

    # Teste PostgreSQL
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                row = cur.fetchone()
                results["postgres"] = (row is not None and row["ok"] == 1)
    except Exception as e:
        logger.error("Falha ao conectar no PostgreSQL: %s", e)

    return results
