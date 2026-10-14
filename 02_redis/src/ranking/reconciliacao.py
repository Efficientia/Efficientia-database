"""Reconciliação e Reconstrução de Rankings via Materialized View do PostgreSQL.

Permite reidratar os Sorted Sets e Hashes do Redis a partir da fonte da verdade
(sc_operacao.mv_analise_mortalidade_mensal) caso o Redis sofra reinicialização,
evicção de memória ou falha de persistência.
"""

import logging
from typing import Optional
import psycopg
import redis

from ..connection import get_db_connection, get_redis_client
from .. import keys

logger = logging.getLogger("efficientia.reconciliacao")


class RankingReconciler:
    """Reconstrutor dos placares do Redis a partir da camada analítica relacional."""

    def __init__(
        self,
        redis_client: Optional[redis.Redis] = None,
        db_conn: Optional[psycopg.Connection] = None,
    ):
        self.redis = redis_client or get_redis_client()
        self.db_conn = db_conn

    def reconciliar_empresa(self, empresa_id: str, ano_mes: Optional[str] = None) -> int:
        """Lê os dados da Materialized View e reescreve os Sorted Sets no Redis."""
        should_close = False
        conn = self.db_conn
        if conn is None or conn.closed:
            conn = get_db_connection()
            should_close = True

        reconciled_count = 0
        try:
            with conn.cursor() as cur:
                query = """
                    SELECT
                        fk_empresa,
                        fk_motorista,
                        TO_CHAR(mes_referencia, 'YYYY-MM') AS ano_mes,
                        volume_animais_mes,
                        total_mortes_mes,
                        taxa_mortalidade_percentual
                    FROM sc_operacao.mv_analise_mortalidade_mensal
                    WHERE fk_empresa = %s
                """
                params = [empresa_id]

                if ano_mes:
                    query += " AND TO_CHAR(mes_referencia, 'YYYY-MM') = %s"
                    params.append(ano_mes)

                query += " ORDER BY mes_referencia DESC;"

                cur.execute(query, tuple(params))
                rows = cur.fetchall()

                if not rows:
                    logger.info("Nenhum dado analítico encontrado na Materialized View para empresa %s.", empresa_id)
                    return 0

                logger.info("Reconciliando %d registro(s) analítico(s) no Redis...", len(rows))

                pipe = self.redis.pipeline()
                for r in rows:
                    m_id = str(r["fk_motorista"])
                    periodo = r["ano_mes"]
                    vol = int(r["volume_animais_mes"] or 0)
                    mortes = int(r["total_mortes_mes"] or 0)
                    taxa = float(r["taxa_mortalidade_percentual"] or 0.0)

                    k_stats = keys.stats_motorista(empresa_id, periodo, m_id)
                    k_vol = keys.ranking_volume(empresa_id, periodo)
                    k_mort = keys.ranking_mortalidade(empresa_id, periodo)

                    pipe.hset(k_stats, mapping={"embarcados": vol, "mortos": mortes})
                    pipe.zadd(k_vol, {m_id: vol})
                    pipe.zadd(k_mort, {m_id: taxa})
                    reconciled_count += 1

                pipe.execute()
                logger.info("Reconciliação concluída com sucesso: %d motoristas atualizados.", reconciled_count)

        finally:
            if should_close and conn and not conn.closed:
                conn.close()

        return reconciled_count
