"""Gerenciador de Rankings em Tempo Real (Leaderboards) com Redis Sorted Sets.

Implementa atualização atômica de contadores via Hashes (HINCRBY) e cálculo
dinâmico de score nos Sorted Sets (ZADD / ZINCRBY), permitindo consultas
instantâneas de pontuação e posição (ZRANK / ZREVRANK) em tempo O(log N).
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import redis

from ..connection import get_redis_client
from .. import keys

logger = logging.getLogger("efficientia.ranking")

DEFAULT_EXPIRATION_DAYS = 90  # 3 meses de histórico nos Sorted Sets


class LeaderboardService:
    """Serviço de cálculo e consulta de rankings de motoristas e unidades."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client or get_redis_client()

    def registrar_viagem_finalizada(
        self,
        empresa_id: str,
        motorista_id: str,
        data_referencia: Optional[str] = None,
        total_embarcados: int = 0,
        qtd_morto: int = 0,
    ) -> Dict[str, Any]:
        """Atualiza estatísticas e rankings do motorista em tempo real."""
        # Determina o período (AAAA-MM)
        if data_referencia:
            try:
                dt = datetime.fromisoformat(data_referencia.replace("Z", ""))
                ano_mes = dt.strftime("%Y-%m")
            except Exception:
                ano_mes = datetime.utcnow().strftime("%Y-%m")
        else:
            ano_mes = datetime.utcnow().strftime("%Y-%m")

        key_stats = keys.stats_motorista(empresa_id, ano_mes, motorista_id)
        key_volume = keys.ranking_volume(empresa_id, ano_mes)
        key_mortalidade = keys.ranking_mortalidade(empresa_id, ano_mes)

        ttl_seconds = DEFAULT_EXPIRATION_DAYS * 86400

        # Executa em pipeline atômico
        pipe = self.redis.pipeline()
        pipe.hincrby(key_stats, "embarcados", total_embarcados)
        pipe.hincrby(key_stats, "mortos", qtd_morto)
        pipe.hincrby(key_stats, "viagens", 1)
        pipe.expire(key_stats, ttl_seconds)

        pipe.zincrby(key_volume, total_embarcados, motorista_id)
        pipe.expire(key_volume, ttl_seconds)

        results = pipe.execute()

        total_acum_embarcados = int(results[0])
        total_acum_mortos = int(results[1])

        # Recalcula taxa de mortalidade ponderada do mês
        taxa = 0.0
        if total_acum_embarcados > 0:
            taxa = round((total_acum_mortos / total_acum_embarcados) * 100, 2)

        # Atualiza o Sorted Set de mortalidade
        self.redis.zadd(key_mortalidade, {motorista_id: taxa})
        self.redis.expire(key_mortalidade, ttl_seconds)

        logger.debug(
            "Ranking atualizado para motorista %s (%s): %d cabeças, taxa mortalidade: %.2f%%",
            motorista_id,
            ano_mes,
            total_acum_embarcados,
            taxa,
        )

        return {
            "motorista_id": motorista_id,
            "ano_mes": ano_mes,
            "total_embarcados": total_acum_embarcados,
            "total_mortos": total_acum_mortos,
            "taxa_mortalidade": taxa,
        }

    def registrar_tempo_descarga(
        self,
        empresa_id: str,
        unidade_id: str,
        data_iso: str,
        tempo_horas: float,
    ) -> None:
        """Registra tempo médio de descarga na unidade frigorífica para ranking diário."""
        key = keys.ranking_descarga(empresa_id, data_iso)
        # Menor tempo = melhor colocação
        self.redis.zadd(key, {unidade_id: round(tempo_horas, 2)})
        self.redis.expire(key, 7 * 86400)  # 7 dias de retenção

    def get_top_volume(self, empresa_id: str, ano_mes: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retorna o Top motoristas que mais transportaram animais no mês (ordem decrescente)."""
        key = keys.ranking_volume(empresa_id, ano_mes)
        raw = self.redis.zrevrange(key, 0, limit - 1, withscores=True)

        ranking = []
        for rank, (motorista_id, volume) in enumerate(raw, start=1):
            ranking.append({
                "posicao": rank,
                "motorista_id": motorista_id,
                "total_cabecas": int(volume),
            })
        return ranking

    def get_top_mortalidade(
        self, empresa_id: str, ano_mes: str, limit: int = 10, menor_mortalidade_primeiro: bool = True
    ) -> List[Dict[str, Any]]:
        """Retorna o ranking de motoristas por taxa de mortalidade no mês."""
        key = keys.ranking_mortalidade(empresa_id, ano_mes)
        if menor_mortalidade_primeiro:
            raw = self.redis.zrange(key, 0, limit - 1, withscores=True)
        else:
            raw = self.redis.zrevrange(key, 0, limit - 1, withscores=True)

        ranking = []
        for rank, (motorista_id, taxa) in enumerate(raw, start=1):
            ranking.append({
                "posicao": rank,
                "motorista_id": motorista_id,
                "taxa_mortalidade_pct": float(taxa),
            })
        return ranking

    def get_posicao_motorista(self, empresa_id: str, ano_mes: str, motorista_id: str) -> Dict[str, Any]:
        """Consulta a posição individual de um condutor no mês."""
        key_volume = keys.ranking_volume(empresa_id, ano_mes)
        key_mortalidade = keys.ranking_mortalidade(empresa_id, ano_mes)

        pos_volume = self.redis.zrevrank(key_volume, motorista_id)
        score_volume = self.redis.zscore(key_volume, motorista_id)

        pos_mortalidade = self.redis.zrank(key_mortalidade, motorista_id)
        score_mortalidade = self.redis.zscore(key_mortalidade, motorista_id)

        return {
            "motorista_id": motorista_id,
            "ano_mes": ano_mes,
            "posicao_volume": (pos_volume + 1) if pos_volume is not None else None,
            "total_cabecas": int(score_volume) if score_volume is not None else 0,
            "posicao_mortalidade": (pos_mortalidade + 1) if pos_mortalidade is not None else None,
            "taxa_mortalidade": float(score_mortalidade) if score_mortalidade is not None else 0.0,
        }
