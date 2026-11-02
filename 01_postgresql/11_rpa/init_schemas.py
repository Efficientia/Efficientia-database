"""
Script auxiliar para inicialização dos esquemas e dados de teste para demonstração e validação do RPA.
Cria as tabelas no Banco 1 (DB1 (Operacional) - Efficientia.sql) e no Banco 2 (DB2 (Corporativo) - Efficientia-database).
"""

from __future__ import annotations
import logging
from datetime import date
from sqlalchemy import text
import uuid
from database import DatabaseManager, db_manager
from models import (
    BaseDB1,
    BaseDB2,
    BaseAudit,
    DB1Empresa,
    DB1Motorista,
    DB2Endereco,
    DB2Empresa,
    DB2Usuario,
)
logger = logging.getLogger("efficientia_rpa.init_schemas")


def create_all_tables(mgr: DatabaseManager | None = None):
    """Cria todas as tabelas em ambos os bancos de dados."""
    manager = mgr or db_manager

    logger.info("Criando tabelas no Banco 1 (DB1 (Operacional) - Efficientia.sql)...")
    BaseDB1.metadata.create_all(manager.engine_db1)

    logger.info("Criando tabelas no Banco 2 (DB2 (Corporativo) - Efficientia-database)...")
    BaseDB2.metadata.create_all(manager.engine_db2)
    BaseAudit.metadata.create_all(manager.engine_db2)

    logger.info("Tabelas criadas com sucesso em ambos os bancos!")

def seed_sample_data(mgr: DatabaseManager | None = None):
    """
    Popula os dois bancos com dados iniciais divergentes para validar a sincronização bidirecional:
      - Banco 1 começa com: Empresa A e Motorista A (João Silva)
      - Banco 2 começa com: Empresa B e Motorista B (Carlos Eduardo)
    Após o RPA rodar, ambos os bancos devem conter Empresa A, Empresa B, Motorista A e Motorista B.
    """
    manager = mgr or db_manager
    session1 = manager.get_db1_session()
    session2 = manager.get_db2_session()

    try:
        # 1. Banco 1 (Operacional): Dados Iniciais
        if session1.query(DB1Empresa).count() == 0:
            logger.info("Populando Banco 1 (Operacional) com dados iniciais de teste...")
            emp1 = DB1Empresa(
                nome="TransBoi Logistica Ltda",
                cnpj="12345678000101",
                codigo="EMP001",
            )
            session1.add(emp1)
            session1.flush()

            mot1 = DB1Motorista(
                id_empresa=emp1.id,
                nome="Carlos Silva",
                data_nascimento=date(1985, 3, 12),
                email="carlos.silva@email.com",
                telefone="11987654321",
                senha="senha123",
                assinatura="hash_ass_mot_01",
            )
            session1.add(mot1)
            session1.commit()
            logger.info("Banco 1 (Operacional) populado com sucesso.")

        # 2. Banco 2 (Corporativo): Dados Iniciais
        if session2.query(DB2Empresa).count() == 0:
            logger.info("Populando Banco 2 (Corporativo) com dados iniciais de teste...")
            end2 = DB2Endereco(
                id=str(uuid.uuid4()),
                cep="01001-000",
                logradouro="Avenida Marginal Direita do Tietê",
                numero="500",
                cidade="São Paulo",
                estado="SP",
            )
            session2.add(end2)
            session2.flush()

            emp2 = DB2Empresa(
                id=str(uuid.uuid4()),
                endereco_id=end2.id,
                nome="JBS Transportes Rodoviários S/A",
                razao_social="JBS S.A. Divisão de Frotas",
                cnpj="02916265000100",
                codigo_interno="JBS-001",
                email="transportes@jbs.com.br",
            )
            session2.add(emp2)
            session2.flush()

            mot2 = DB2Usuario(
                id=str(uuid.uuid4()),
                tipo="motorista",
                empresa_id=emp2.id,
                cargo="Motorista",
                nivel_acesso="conducao",
                nome_completo="João da Silva Ferreira",
                cpf="11122233344",
                data_nascimento=date(1985, 4, 12),
                email="joao.ferreira@jbs.com.br",
                telefone="11987654321",
                senha_hash="$2a$10$hashSimuladoSenhaMotorista1",
                status_cadastro="ativo",
            )
            session2.add(mot2)
            session2.commit()
            logger.info("Banco 2 (Corporativo) populado com sucesso.")
    finally:
        session1.close()
        session2.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    create_all_tables()
    seed_sample_data()
