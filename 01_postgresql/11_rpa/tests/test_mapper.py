"""
Testes unitários para o módulo de mapeamento e normalização (mapper.py).
"""

from datetime import date
from mapper import (
    clean_cnpj,
    clean_cpf,
    clean_email,
    compute_content_hash,
    DataMapper,
)


def test_clean_cnpj():
    assert clean_cnpj("02.916.265/0001-00") == "02916265000100"
    assert clean_cnpj("02916265000100") == "02916265000100"
    assert clean_cnpj("123") == "123"
    assert clean_cnpj(None) == ""


def test_clean_cpf():
    assert clean_cpf("111.222.333-44") == "11122233344"
    assert clean_cpf("11122233344") == "11122233344"
    assert clean_cpf(None) == ""


def test_clean_email():
    assert clean_email("  User.Test@Example.Com  ") == "user.test@example.com"
    assert clean_email(None) == ""


def test_compute_content_hash():
    d1 = {"a": 1, "b": "texto", "c": date(2026, 1, 1)}
    d2 = {"c": date(2026, 1, 1), "b": "texto", "a": 1}
    # Ordem das chaves não deve afetar o hash
    assert compute_content_hash(d1) == compute_content_hash(d2)

    # Mudança no valor deve alterar o hash
    d3 = {"a": 2, "b": "texto", "c": date(2026, 1, 1)}
    assert compute_content_hash(d1) != compute_content_hash(d3)


def test_empresa_db1_to_db2():
    source = {
        "nome": "Frigorífico Boi Gordo",
        "cnpj": "98.765.432/0001-10",
        "codigo": "BOI-GORDO",
    }
    result = DataMapper.empresa_db1_to_db2(source, default_password_hash="pwd_hash_123")
    assert result["nome"] == "Frigorífico Boi Gordo"
    assert result["razao_social"] == "Frigorífico Boi Gordo"
    assert result["cnpj"] == "98765432000110"
    assert result["codigo_interno"] == "BOI-GORDO"
    assert result["ativo"] is True
    assert result["senha_hash"] == "pwd_hash_123"


def test_empresa_db2_to_db1():
    source = {
        "nome": "Transportadora Boiadeiro",
        "razao_social": "Boiadeiro Transportes LTDA",
        "cnpj": "12.345.678/0001-90",
        "codigo_interno": "BOI-01",
    }
    result = DataMapper.empresa_db2_to_db1(source)
    assert result["nome"] == "Transportadora Boiadeiro"
    assert result["cnpj"] == "12345678000190"
    assert result["codigo"] == "BOI-01"


def test_motorista_db1_to_db2():
    source = {
        "id": 15,
        "nome": "Lucas Silveira",
        "data_nascimento": date(1992, 11, 20),
        "email": "lucas@fazenda.com",
        "telefone": "19998765432",
        "senha": "senhaOriginal",
    }
    result = DataMapper.motorista_db1_to_db2(source, target_empresa_id=7, default_password_hash="pwd_hash")
    assert result["tipo"] == "motorista"
    assert result["empresa_id"] == 7
    assert result["nome"] == "Lucas Silveira"
    assert result["cpf"] == "99000000015"
    assert result["email"] == "lucas@fazenda.com"
    assert result["telefone"] == "19998765432"
    assert result["ativo"] is True


def test_motorista_db2_to_db1():
    source = {
        "nome": "Marcos Antônio",
        "cpf": "123.456.789-00",
        "email": "marcos@transporte.com",
        "telefone": "11987654321",
        "data_nascimento": date(1980, 5, 10),
        "senha_hash": "hash123",
    }
    result = DataMapper.motorista_db2_to_db1(source, target_empresa_id=42)
    assert result["id_empresa"] == 42
    assert result["nome"] == "Marcos Antônio"
    assert result["email"] == "marcos@transporte.com"
    assert result["telefone"] == "11987654321"
    assert result["data_nascimento"] == date(1980, 5, 10)
    assert result["senha"] == "hash123"
    assert result["cpf"] == "12345678900"

def test_get_divergences():
    current = {"nome": "Empresa A", "telefone": "1199999999"}
    new = {"nome": "Empresa A", "telefone": "1188888888"}

    diffs = DataMapper.get_divergences(current, new, ["nome", "telefone"])
    assert "nome" not in diffs
    assert "telefone" in diffs
    assert diffs["telefone"] == ("1199999999", "1188888888")
