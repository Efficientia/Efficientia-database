"""
Gerenciamento de conexões e sessões de banco de dados para o RPA.
"""

from __future__ import annotations
import logging
from typing import Generator
from sqlalchemy import create_engine, Engine, inspect
from sqlalchemy.orm import sessionmaker, Session
from config import settings

logger = logging.getLogger("efficientia_rpa.database")


class DatabaseManager:
    """Gerencia as engines e sessões dos dois bancos de dados."""

    def __init__(self, db1_url: str | None = None, db2_url: str | None = None):
        self.db1_url = db1_url or settings.db1_url
        self.db2_url = db2_url or settings.db2_url

        # Configura Engine 1
        self.engine_db1: Engine = create_engine(
            self.db1_url,
            pool_pre_ping=True,
            future=True,
        )

        # Configura Engine 2
        self.engine_db2: Engine = create_engine(
            self.db2_url,
            pool_pre_ping=True,
            future=True,
        )
        # Suporte a schema translation para SQLite em memória e testes
        if self.engine_db1.dialect.name == "sqlite":
            self.engine_db1 = self.engine_db1.execution_options(
                schema_translate_map={"sc_corporativo": None, "sc_auditoria": None}
            )
        if self.engine_db2.dialect.name == "sqlite":
            self.engine_db2 = self.engine_db2.execution_options(
                schema_translate_map={"sc_corporativo": None, "sc_auditoria": None}
            )

        self.SessionDB1 = sessionmaker(
            bind=self.engine_db1,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

        self.SessionDB2 = sessionmaker(
            bind=self.engine_db2,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )

    def get_db1_session(self) -> Session:
        return self.SessionDB1()

    def get_db2_session(self) -> Session:
        return self.SessionDB2()

    def inspect_db1_tables(self) -> list[str]:
        insp = inspect(self.engine_db1)
        return insp.get_table_names()

    def inspect_db2_tables(self) -> list[str]:
        insp = inspect(self.engine_db2)
        return insp.get_table_names()

    def inspect_columns(self, engine: Engine, table_name: str) -> list[str]:
        insp = inspect(engine)
        if insp.has_table(table_name):
            return [col["name"] for col in insp.get_columns(table_name)]
        return []

    def close(self):
        self.engine_db1.dispose()
        self.engine_db2.dispose()


# Instância global padrão
db_manager = DatabaseManager()
