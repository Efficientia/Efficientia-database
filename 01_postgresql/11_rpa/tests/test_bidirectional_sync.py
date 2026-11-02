"""
Testes de integração ponta a ponta da sincronização bidirecional do RPA.
Utiliza dois bancos SQLite em memória para isolamento completo.
Banco 1: DB1 (Operacional) (Efficientia.sql - empresa, motorista)
Banco 2: DB2 (Corporativo) (Efficientia-database - empresa, usuario)
"""

from datetime import date
import pytest
from database import DatabaseManager
from models import (
    BaseDB1,
    BaseDB2,
    BaseAudit,
    DB1Empresa,
    DB1Motorista,
    DB2Empresa,
    DB2Usuario,
)
from syncer import DatabaseSyncer


@pytest.fixture
def test_mgr():
    """Cria um DatabaseManager com dois bancos SQLite em memória para teste."""
    mgr = DatabaseManager(
        db1_url="sqlite:///file:mem_db1?mode=memory&cache=shared&uri=true",
        db2_url="sqlite:///file:mem_db2?mode=memory&cache=shared&uri=true",
    )
    # Cria as tabelas
    BaseDB1.metadata.create_all(mgr.engine_db1)
    BaseAudit.metadata.create_all(mgr.engine_db2)
    BaseDB2.metadata.create_all(mgr.engine_db2)

    yield mgr

    # Limpeza
    BaseDB1.metadata.drop_all(mgr.engine_db1)
    BaseAudit.metadata.drop_all(mgr.engine_db2)
    BaseDB2.metadata.drop_all(mgr.engine_db2)
    mgr.close()


def _populate_test_data(test_mgr):
    s1 = test_mgr.get_db1_session()
    s2 = test_mgr.get_db2_session()

    # Banco 1 (Operacional)
    emp1 = DB1Empresa(
        nome="TransBoi Logistica Ltda",
        cnpj="12345678000101",
        codigo="EMP001",
    )
    s1.add(emp1)
    s1.commit()

    mot1 = DB1Motorista(
        id_empresa=emp1.id,
        nome="Carlos Silva",
        email="carlos@transboi.com",
        telefone="11987654321",
        data_nascimento=date(1985, 3, 12),
        senha="senhaCarlos123",
        assinatura="hash123",
    )
    s1.add(mot1)
    s1.commit()

    # Banco 2 (Corporativo)
    emp2 = DB2Empresa(
        nome="JBS Transportes Rodoviários S/A",
        razao_social="JBS S.A.",
        cnpj="02916265000100",
        codigo_interno="JBS-01",
        email="contato@jbs.com",
        senha_hash="pwd123",
        ativo=True,
    )
    s2.add(emp2)
    s2.commit()

    mot2 = DB2Usuario(
        tipo="motorista",
        empresa_id=emp2.id,
        nome="João da Silva Ferreira",
        cpf="11122233344",
        email="joao@jbs.com",
        telefone="11999991111",
        data_nascimento=date(1985, 1, 15),
        senha_hash="pwdmot123",
        ativo=True,
    )
    s2.add(mot2)
    s2.commit()

    s1.close()
    s2.close()


def test_bidirectional_sync_flow(test_mgr):
    """
    Testa o ciclo completo:
      1. DB1 (DB1 (Operacional)) tem TransBoi (Empresa 1) e Carlos (Motorista 1).
      2. DB2 (DB2 (Corporativo)) tem JBS (Empresa 2) e João (Motorista 2).
      3. O RPA sincroniza:
         - DB2 deve receber TransBoi e Carlos.
         - DB1 deve receber JBS e João.
      4. As chaves estrangeiras devem ser resolvidas corretamente.
    """
    _populate_test_data(test_mgr)

    # Executa o RPA
    syncer = DatabaseSyncer(manager=test_mgr)
    report = syncer.run_sync_cycle()

    assert report.status == "SUCCESS"
    assert report.empresa_db1_to_db2.inserted == 1
    assert report.empresa_db2_to_db1.inserted == 1
    assert report.motorista_db1_to_db2.inserted == 1
    assert report.motorista_db2_to_db1.inserted == 1

    # Valida Banco 1 (Operacional)
    s1 = test_mgr.get_db1_session()
    b1_empresas = s1.query(DB1Empresa).all()
    b1_motoristas = s1.query(DB1Motorista).all()

    assert len(b1_empresas) == 2
    cnpjs_b1 = {e.cnpj for e in b1_empresas}
    assert "12345678000101" in cnpjs_b1
    assert "02916265000100" in cnpjs_b1

    assert len(b1_motoristas) == 2
    emails_b1 = {m.email for m in b1_motoristas}
    assert "carlos@transboi.com" in emails_b1
    assert "joao@jbs.com" in emails_b1

    # Valida FK do motorista João no Banco 1: deve apontar para o ID local da JBS no Banco 1!
    jbs_b1 = s1.query(DB1Empresa).filter(DB1Empresa.cnpj == "02916265000100").first()
    joao_b1 = s1.query(DB1Motorista).filter(DB1Motorista.email == "joao@jbs.com").first()
    assert joao_b1.id_empresa == jbs_b1.id

    # Valida Banco 2 (Corporativo)
    s2 = test_mgr.get_db2_session()
    b2_empresas = s2.query(DB2Empresa).all()
    b2_motoristas = s2.query(DB2Usuario).filter(DB2Usuario.tipo == "motorista").all()

    assert len(b2_empresas) == 2
    cnpjs_b2 = {e.cnpj for e in b2_empresas}
    assert "12345678000101" in cnpjs_b2
    assert "02916265000100" in cnpjs_b2

    assert len(b2_motoristas) == 2
    emails_b2 = {m.email for m in b2_motoristas}
    assert "carlos@transboi.com" in emails_b2
    assert "joao@jbs.com" in emails_b2

    # Valida FK do motorista Carlos no Banco 2: deve apontar para o ID local da TransBoi no Banco 2!
    transboi_b2 = s2.query(DB2Empresa).filter(DB2Empresa.cnpj == "12345678000101").first()
    carlos_b2 = s2.query(DB2Usuario).filter(DB2Usuario.email == "carlos@transboi.com").first()
    assert carlos_b2.empresa_id == transboi_b2.id

    s1.close()
    s2.close()


def test_idempotency_second_run(test_mgr):
    """
    Garante que executar a sincronização consecutivamente não cria duplicatas
    nem atualiza dados inalterados (idempotência perfeita).
    """
    syncer = DatabaseSyncer(manager=test_mgr)
    _populate_test_data(test_mgr)

    # 1ª execução
    rep1 = syncer.run_sync_cycle()

    # 2ª execução imediata
    rep2 = syncer.run_sync_cycle()

    assert rep2.status == "SUCCESS"
    assert rep2.empresa_db1_to_db2.inserted == 0
    assert rep2.empresa_db1_to_db2.updated == 0
    assert rep2.empresa_db2_to_db1.inserted == 0
    assert rep2.empresa_db2_to_db1.updated == 0

    assert rep2.motorista_db1_to_db2.inserted == 0
    assert rep2.motorista_db1_to_db2.updated == 0
    assert rep2.motorista_db2_to_db1.inserted == 0
    assert rep2.motorista_db2_to_db1.updated == 0


def test_update_propagation(test_mgr):
    """
    Testa se atualizações nos dados de um banco propagam para o outro:
      - Altera nome da Empresa 1 no Banco 1 (Operacional) -> Deve atualizar no Banco 2 (Corporativo).
      - Altera telefone do Motorista 2 no Banco 2 (Corporativo) -> Deve atualizar no Banco 1 (Operacional).
    """
    _populate_test_data(test_mgr)
    DatabaseSyncer(manager=test_mgr).run_sync_cycle()
    s1 = test_mgr.get_db1_session()
    s2 = test_mgr.get_db2_session()

    # Altera nome da TransBoi no Banco 1 (Operacional)
    transboi1 = s1.query(DB1Empresa).filter(DB1Empresa.cnpj == "12345678000101").first()
    transboi1.nome = "TransBoi Express Renovada"
    s1.commit()

    # Altera telefone de João no Banco 2 (Corporativo)
    joao2 = s2.query(DB2Usuario).filter(DB2Usuario.email == "joao@jbs.com").first()
    joao2.telefone = "11999998888"
    s2.commit()

    s1.close()
    s2.close()

    # Executa RPA
    syncer = DatabaseSyncer(manager=test_mgr)
    report = syncer.run_sync_cycle()

    assert report.status == "SUCCESS"
    assert report.empresa_db1_to_db2.updated == 1
    assert report.motorista_db2_to_db1.updated == 1

    # Verifica no Banco 2 (Corporativo)
    s2 = test_mgr.get_db2_session()
    transboi2 = s2.query(DB2Empresa).filter(DB2Empresa.cnpj == "12345678000101").first()
    assert transboi2.nome == "TransBoi Express Renovada"
    s2.close()

    # Verifica no Banco 1 (Operacional)
    s1 = test_mgr.get_db1_session()
    joao1 = s1.query(DB1Motorista).filter(DB1Motorista.email == "joao@jbs.com").first()
    assert joao1.telefone == "11999998888"
    s1.close()


def test_dry_run_mode(test_mgr):
    """
    Garante que o modo dry-run simula e detecta operações sem aplicar
    quaisquer alterações aos bancos de dados.
    """
    s1 = test_mgr.get_db1_session()
    # Adiciona nova empresa no Banco 1 (Operacional)
    nova_emp = DB1Empresa(
        nome="Nova Transportadora DB1 (Operacional) Teste",
        cnpj="99999999000199",
        codigo="NOV-99",
    )
    s1.add(nova_emp)
    s1.commit()
    s1.close()

    # Executa RPA em modo dry-run
    syncer = DatabaseSyncer(manager=test_mgr, dry_run=True)
    report = syncer.run_sync_cycle()

    # O relatório deve contabilizar a inserção simulada
    assert report.empresa_db1_to_db2.inserted == 1

    # Mas o Banco 2 (Corporativo) NÃO deve ter recebido a empresa
    s2 = test_mgr.get_db2_session()
    emp_db2 = s2.query(DB2Empresa).filter(DB2Empresa.cnpj == "99999999000199").first()
    assert emp_db2 is None
    s2.close()
