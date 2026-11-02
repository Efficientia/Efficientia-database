"""
Modelos de dados e schemas para o Banco 1 e Banco 2.
Baseado em:
 - Banco 1: DB1 (Operacional) (Efficientia.sql - tabelas 'empresa' e 'motorista')
 - Banco 2: DB2 (Corporativo) (Efficientia-database - tabelas 'empresa' e 'usuario' tipo motorista)
"""

import uuid
from datetime import datetime, date, timezone
from typing import Optional
from sqlalchemy import (
    MetaData,
    Table,
    Column,
    Integer,
    String,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Text,
    Enum as SAEnum,
)
from sqlalchemy.orm import declarative_base

BaseDB1 = declarative_base()
BaseDB2 = declarative_base()
BaseAudit = declarative_base()

TipoUsuarioEnum = SAEnum(
    "administrador", "motorista", "manobrista", "analista", "pecuarista", "curraleiro",
    name="ty_tipo_usuario",
    schema="sc_corporativo",
    inherit_schema=True,
    values_callable=lambda x: [e.value if hasattr(e, "value") else str(e) for e in x],
)

NivelAcessoEnum = SAEnum(
    "administrativo", "auditoria", "conducao",
    name="ty_nivel_acesso",
    schema="sc_corporativo",
    inherit_schema=True,
)

CategoriaCnhEnum = SAEnum(
    "a", "b", "c", "d", "e",
    name="ty_categoria_cnh",
    schema="sc_corporativo",
    inherit_schema=True,
)

BaseDB1 = declarative_base()
BaseDB2 = declarative_base()
BaseAudit = declarative_base()


# ==============================================================================
# BANCO 1: INSTANCIA OPERACIONAL (Efficientia.sql - Logística Operacional)
# ==============================================================================
class DB1Empresa(BaseDB1):
    """
    Tabela 'empresa' no Banco 1 (DB1 / Instancia Operacional):
    id SERIAL PRIMARY KEY,
    nome VARCHAR(150) UNIQUE NOT NULL,
    cnpj CHAR(14) UNIQUE NOT NULL,
    codigo VARCHAR(20) UNIQUE
    """
    __tablename__ = "empresa"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(150), unique=True, nullable=False)
    cnpj = Column(String(14), unique=True, nullable=False)
    codigo = Column(String(20), unique=True, nullable=True)


class DB1Motorista(BaseDB1):
    """
    Tabela 'motorista' no Banco 1 (DB1 / Instancia Operacional):
    id SERIAL PRIMARY KEY,
    id_empresa INTEGER NOT NULL REFERENCES empresa(id),
    assinatura VARCHAR(128),
    nome VARCHAR(150) NOT NULL,
    data_nascimento DATE NOT NULL,
    senha VARCHAR(100) NOT NULL,
    email VARCHAR(254) UNIQUE NOT NULL,
    telefone VARCHAR(20) NOT NULL
    """
    __tablename__ = "motorista"

    id = Column(Integer, primary_key=True, autoincrement=True)
    id_empresa = Column(Integer, ForeignKey("empresa.id", ondelete="CASCADE"), nullable=False)
    assinatura = Column(String(128), nullable=True)
    nome = Column(String(150), nullable=False)
    data_nascimento = Column(Date, nullable=False)
    senha = Column(String(100), nullable=False)
    email = Column(String(254), unique=True, nullable=False)
    telefone = Column(String(20), nullable=False)


# ==============================================================================
# BANCO 2: INSTANCIA CORPORATIVA (Efficientia-database - Corporativo / Web / Mobile)
# ==============================================================================
class DB2Endereco(BaseDB2):
    """
    Tabela 'tb_endereco' no Banco 2 (DB2 / sc_corporativo conforme Efficientia-database):
    id UUID, cep VARCHAR(10), logradouro VARCHAR(150), numero VARCHAR(20), cidade VARCHAR(100), estado VARCHAR(2)
    """
    __tablename__ = "tb_endereco"
    __table_args__ = {"schema": "sc_corporativo"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cep = Column(String(10), nullable=False)
    logradouro = Column(String(150), nullable=False)
    numero = Column(String(20), nullable=False)
    cidade = Column(String(100), nullable=False)
    estado = Column(String(2), nullable=False)

    def __init__(self, **kwargs):
        known_cols = {"id", "cep", "logradouro", "numero", "cidade", "estado"}
        for k, v in kwargs.items():
            if k in known_cols:
                setattr(self, k, v)


class DB2Empresa(BaseDB2):
    """
    Tabela 'tb_empresa' no Banco 2 (DB2 / sc_corporativo conforme Efficientia-database):
    id UUID, endereco_id UUID, nome VARCHAR(150), razao_social VARCHAR(150),
    codigo_interno VARCHAR(20), email VARCHAR(150), cnpj VARCHAR(14)
    """
    __tablename__ = "tb_empresa"
    __table_args__ = {"schema": "sc_corporativo"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    endereco_id = Column(String(36), ForeignKey("sc_corporativo.tb_endereco.id"), nullable=True)
    nome = Column(String(150), nullable=True)
    razao_social = Column(String(150), nullable=True)
    codigo_interno = Column(String(20), unique=True, nullable=False)
    email = Column(String(150), unique=True, nullable=True)
    cnpj = Column(String(14), unique=True, nullable=False)

    def __init__(self, **kwargs):
        known_cols = {"id", "endereco_id", "nome", "razao_social", "codigo_interno", "email", "cnpj"}
        for k, v in kwargs.items():
            if k in known_cols:
                setattr(self, k, v)


class DB2Usuario(BaseDB2):
    """
    Tabela 'tb_usuario' no Banco 2 (DB2 / sc_corporativo conforme Efficientia-database):
    O motorista corporativo é armazenado com tipo = 'motorista'.
    """
    __tablename__ = "tb_usuario"
    __table_args__ = {"schema": "sc_corporativo"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    empresa_id = Column(String(36), ForeignKey("sc_corporativo.tb_empresa.id"), nullable=False)
    tipo = Column(TipoUsuarioEnum, nullable=False, default="motorista")
    cargo = Column(String(150), nullable=False, default="Motorista")
    nivel_acesso = Column(NivelAcessoEnum, nullable=False, default="conducao")
    cpf = Column(String(11), unique=True, nullable=False)
    cnh_numero = Column(String(20), nullable=True)
    categoria_cnh = Column(CategoriaCnhEnum, nullable=True)
    data_vencimento_cnh = Column(Date, nullable=True)
    nome_completo = Column(String(250), nullable=False)
    data_nascimento = Column(Date, nullable=True)
    email = Column(String(150), unique=True, nullable=True)
    telefone = Column(String(20), nullable=True)
    senha_hash = Column(String(255), nullable=False)
    url_assinatura_geral = Column(Text, nullable=True)
    status_cadastro = Column(String(20), nullable=False, default="ativo")

    @property
    def nome(self) -> str:
        return self.nome_completo

    @nome.setter
    def nome(self, val: str):
        self.nome_completo = val

    def __init__(self, **kwargs):
        if "nome" in kwargs and "nome_completo" not in kwargs:
            kwargs["nome_completo"] = kwargs.pop("nome")
        known_cols = {
            "id", "empresa_id", "tipo", "cargo", "nivel_acesso", "cpf",
            "cnh_numero", "categoria_cnh", "data_vencimento_cnh", "nome_completo",
            "data_nascimento", "email", "telefone", "senha_hash",
            "url_assinatura_geral", "status_cadastro"
        }
        for k, v in kwargs.items():
            if k in known_cols:
                setattr(self, k, v)


class DB2Caminhoneiro(BaseDB2):
    """Fallback opcional se o Banco 2 usar tabela 'caminhoneiro'."""
    __tablename__ = "caminhoneiro"
    __table_args__ = {"schema": "sc_corporativo"}

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    empresa_id = Column(String(36), ForeignKey("sc_corporativo.tb_empresa.id"), nullable=True)
    nome = Column(String(150), nullable=False)
    cpf = Column(String(11), unique=True, nullable=True)
    codigo_interno = Column(String(50), unique=True, nullable=True)
    data_nascimento = Column(Date, nullable=True)
    email = Column(String(150), unique=True, nullable=True)
    telefone = Column(String(20), nullable=True)
    senha_hash = Column(String(255), nullable=True)
    ativo = Column(Boolean, default=True, nullable=False)
# ==============================================================================
# TABELA DE AUDITORIA E LOG DO RPA
# ==============================================================================
class RPASyncLog(BaseAudit):
    """Tabela de log de auditoria das execuções e alterações realizadas pelo RPA."""
    __tablename__ = "rpa_sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(50), nullable=False)  # 'empresa' ou 'motorista'
    source_db = Column(String(10), nullable=False)    # 'db1' ou 'db2'
    target_db = Column(String(10), nullable=False)    # 'db1' ou 'db2'
    source_id = Column(String(50), nullable=False)
    target_id = Column(String(50), nullable=True)
    natural_key = Column(String(100), nullable=False) # CNPJ, CPF ou Email
    action = Column(String(20), nullable=False)       # 'INSERT', 'UPDATE', 'SKIPPED'
    data_hash = Column(String(64), nullable=True)
    synced_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    error_message = Column(Text, nullable=True)
