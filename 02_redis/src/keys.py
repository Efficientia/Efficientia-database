"""Módulo padronizador de convenção de nomes de chaves no Redis (Multi-Tenant).

Padrão: efficientia:{env}:{empresa_id}:{recurso}:{detalhes}
Garante isolamento absoluto por tenant e por ambiente (dev/stage/prod).
"""

from typing import Union
from uuid import UUID
from .config import settings

CONSUMER_GROUP_NAME = "efficientia_event_consumers"


def _format_id(val: Union[str, UUID]) -> str:
    return str(val).strip().lower()


def stream_eventos(empresa_id: Union[str, UUID]) -> str:
    """Chave da Stream de eventos principal de uma empresa."""
    return f"efficientia:{settings.app_env}:{_format_id(empresa_id)}:stream:eventos"


def stream_dlq(empresa_id: Union[str, UUID]) -> str:
    """Chave da Dead Letter Queue (DLQ) para mensagens que excederam tentativas."""
    return f"efficientia:{settings.app_env}:{_format_id(empresa_id)}:stream:dlq"


def ranking_mortalidade(empresa_id: Union[str, UUID], ano_mes: str) -> str:
    """Chave do Sorted Set de taxa de mortalidade dos motoristas no mês (AAAA-MM)."""
    return f"efficientia:{settings.app_env}:{_format_id(empresa_id)}:ranking:mortalidade:{ano_mes}"


def ranking_volume(empresa_id: Union[str, UUID], ano_mes: str) -> str:
    """Chave do Sorted Set de total de cabeças transportadas por motorista no mês (AAAA-MM)."""
    return f"efficientia:{settings.app_env}:{_format_id(empresa_id)}:ranking:volume:{ano_mes}"


def stats_motorista(empresa_id: Union[str, UUID], ano_mes: str, motorista_id: Union[str, UUID]) -> str:
    """Chave Hash com os contadores de viagens, embarques e mortes do motorista no mês."""
    return f"efficientia:{settings.app_env}:{_format_id(empresa_id)}:stats:motorista:{ano_mes}:{_format_id(motorista_id)}"


def ranking_descarga(empresa_id: Union[str, UUID], data_iso: str) -> str:
    """Chave do Sorted Set de tempo médio de descarga (horas) por unidade frigorífica no dia."""
    return f"efficientia:{settings.app_env}:{_format_id(empresa_id)}:ranking:descarga:{data_iso}"


def cache_config(empresa_id: Union[str, UUID]) -> str:
    """Chave de cache das parametrizações operacionais da empresa."""
    return f"efficientia:{settings.app_env}:{_format_id(empresa_id)}:config"


def lock_job(empresa_id: Union[str, UUID], job_key: str) -> str:
    """Chave para lock distribuído de tarefas concorrentes."""
    return f"efficientia:{settings.app_env}:{_format_id(empresa_id)}:lock:{job_key}"


def rate_limit_report(usuario_id: Union[str, UUID]) -> str:
    """Chave para controle de taxa (rate limiting) de envio de relatórios por usuário."""
    return f"efficientia:{settings.app_env}:ratelimit:report:{_format_id(usuario_id)}"
