"""Interface base para processadores de eventos de fila."""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseJob(ABC):
    """Classe base para execução de tarefas assíncronas."""

    @abstractmethod
    def can_handle(self, tipo_evento: str) -> bool:
        """Determina se o job tem interesse neste tipo de evento."""
        pass

    @abstractmethod
    def process(self, event_data: Dict[str, Any]) -> bool:
        """Executa a lógica de negócio do job. Retorna True em caso de sucesso."""
        pass
