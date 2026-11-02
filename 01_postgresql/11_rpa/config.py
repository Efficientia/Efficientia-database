"""
Configurações do RPA de Sincronização Bidirecional entre Banco 1 e Banco 2.
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Carrega .env se existir
env_path = Path(".env")
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    load_dotenv(override=True)


@dataclass
class Settings:
    # Banco 1 (Instancia Operacional - Logistica Operacional (DB1))
    db1_url: str = os.getenv("DB1_URL", "sqlite:///db1_operacional.db")
    db1_empresa_table: str = os.getenv("DB1_EMPRESA_TABLE", "empresa")
    db1_motorista_table: str = os.getenv("DB1_MOTORISTA_TABLE", "motorista")

    # Banco 2 (Instancia Corporativa - Corporativo / Web / Mobile (DB2))
    db2_url: str = os.getenv("DB2_URL", "sqlite:///db2_corporativo.db")
    db2_empresa_table: str = os.getenv("DB2_EMPRESA_TABLE", "tb_empresa")
    db2_motorista_table: str = os.getenv("DB2_MOTORISTA_TABLE", "tb_usuario")
    # RPA Runtime
    sync_interval_seconds: int = int(os.getenv("SYNC_INTERVAL_SECONDS", "30"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Senha padrão temporária para novos registros criados pela sincronização
    default_sync_password_hash: str = os.getenv(
        "DEFAULT_SYNC_PASSWORD_HASH",
        "$2a$10$abcdefghijklmnopqrstuvwxyz1234567890"  # Hash simulado / bcrypt
    )


settings = Settings()
