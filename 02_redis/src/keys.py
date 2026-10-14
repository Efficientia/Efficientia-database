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


def cache_config(empresa_id: Union[str, UUID]) -> str:
    """Chave de cache das parametrizações operacionais da empresa."""
    return f"efficientia:{settings.app_env}:{_format_id(empresa_id)}:config"


def lock_job(empresa_id: Union[str, UUID], job_key: str) -> str:
    """Chave para lock distribuído de tarefas concorrentes."""
    return f"efficientia:{settings.app_env}:{_format_id(empresa_id)}:lock:{job_key}"
