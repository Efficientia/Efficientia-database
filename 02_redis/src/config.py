import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega o .env localizado na raiz de 02_redis ou na raiz do repositório
_env_path = Path(__file__).resolve().parent.parent / ".env"
if not _env_path.exists():
    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(_env_path)


class Settings:
    """Configurações da aplicação carregadas de variáveis de ambiente."""

    def __init__(self):
        self.app_env: str = os.getenv("APP_ENV", "development")
        self.redis_url: str = os.getenv(
            "REDIS_URL", "rediss://default:token@localhost:6379"
        )
        self.database_url: str = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:postgres@localhost:5432/postgres",
        )
        self.relay_poll_interval: float = float(
            os.getenv("RELAY_POLL_INTERVAL_SECONDS", "2.0")
        )
        self.relay_batch_size: int = int(os.getenv("RELAY_BATCH_SIZE", "25"))
        self.worker_block_ms: int = int(os.getenv("WORKER_BLOCK_MS", "5000"))
        self.max_job_retries: int = int(os.getenv("MAX_JOB_RETRIES", "3"))

    def validate(self) -> None:
        """Valida se as URLs essenciais foram fornecidas."""
        if not self.redis_url or "localhost" in self.redis_url and self.app_env == "production":
            raise ValueError("REDIS_URL de produção não pode ser padrão/vazia.")
        if not self.database_url:
            raise ValueError("DATABASE_URL não configurada.")


settings = Settings()
