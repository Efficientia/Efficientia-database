"""
Módulo de mapeamento, normalização e transformação de dados entre Banco 1 e Banco 2.
"""

from __future__ import annotations
import re
import hashlib
import json
from datetime import date, datetime
from typing import Any


def clean_cnpj(value: Any) -> str:
    """Extrai apenas os dígitos de um CNPJ e garante até 14 caracteres."""
    if value is None:
        return ""
    digits = re.sub(r"\D", "", str(value))
    if len(digits) > 14:
        return digits[:14]
    return digits


def clean_cpf(value: Any) -> str:
    """Extrai apenas os dígitos de um CPF e garante até 11 caracteres."""
    if value is None:
        return ""
    digits = re.sub(r"\D", "", str(value))
    if len(digits) > 11:
        return digits[:11]
    return digits


def clean_email(value: Any) -> str:
    """Normaliza o e-mail em minúsculas e remove espaços."""
    if not value:
        return ""
    return str(value).strip().lower()


def compute_content_hash(data: dict[str, Any]) -> str:
    """Gera um hash SHA-256 estável para comparação de conteúdo entre bancos."""
    normalized: dict[str, Any] = {}
    for k, v in sorted(data.items()):
        if isinstance(v, (date, datetime)):
            normalized[k] = v.isoformat()
        else:
            normalized[k] = str(v) if v is not None else ""
    raw = json.dumps(normalized, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def compute_empresa_hash(nome: str, cnpj: str, codigo: str | None = None) -> str:
    """Gera hash canônico para a entidade Empresa considerando os campos comuns entre os bancos."""
    return compute_content_hash({
        "cnpj": clean_cnpj(cnpj),
        "nome": (nome or "").strip(),
        "codigo": (codigo or "").strip(),
    })


def compute_motorista_hash(
    nome: str,
    email: str | None = None,
    telefone: str | None = None,
    data_nascimento: Any = None,
    cpf: str | None = None,
) -> str:
    """Gera hash canônico para Motorista considerando os campos comuns entre bancos."""
    dt_str = ""
    if data_nascimento is not None:
        if hasattr(data_nascimento, "isoformat"):
            dt_str = data_nascimento.isoformat()
        else:
            dt_str = str(data_nascimento).strip()
    return compute_content_hash({
        "nome": (nome or "").strip(),
        "email": clean_email(email),
        "telefone": str(telefone or "").strip(),
        "data_nascimento": dt_str,
    })


class DataMapper:
    """Transformador e conversor de entidades entre as estruturas do Banco 1 (Operacional) e Banco 2 (Corporativo)."""

    # --------------------------------------------------------------------------
    # EMPRESA
    # --------------------------------------------------------------------------
    @staticmethod
    def empresa_db1_to_db2(source: dict[str, Any], default_password_hash: str) -> dict[str, Any]:
        """
        Converte Empresa do Banco 1 (DB1 / Instancia Operacional) para Banco 2 (DB2 / Instancia Corporativa).
        Banco 2 espera: nome, razao_social, cnpj, codigo_interno, ativo, senha_hash, email, etc.
        """
        raw_cnpj = clean_cnpj(source.get("cnpj"))
        codigo = source.get("codigo") or source.get("codigo_interno") or (f"EMP-{raw_cnpj[-6:]}" if len(raw_cnpj) >= 6 else f"EMP-{raw_cnpj}")
        nome = (source.get("nome") or "Empresa Transportadora").strip()

        return {
            "nome": nome,
            "razao_social": nome,
            "nome_fantasia": nome,
            "cnpj": raw_cnpj,
            "codigo_interno": str(codigo).strip(),
            "ativo": True,
            "senha_hash": default_password_hash,
            "email": f"contato_{raw_cnpj}@efficientia.com.br",
        }

    @staticmethod
    def empresa_db2_to_db1(source: dict[str, Any]) -> dict[str, Any]:
        """
        Converte Empresa do Banco 2 (DB2 / Instancia Corporativa) para Banco 1 (DB1 / Instancia Operacional).
        Banco 1 espera: nome (varchar 150), cnpj (char 14), codigo (varchar 20)
        """
        raw_cnpj = clean_cnpj(source.get("cnpj"))
        codigo = source.get("codigo_interno") or source.get("codigo")
        if not codigo:
            codigo = f"EMP-{raw_cnpj[-6:]}" if len(raw_cnpj) >= 6 else f"EMP-{raw_cnpj}"

        nome = source.get("nome") or source.get("razao_social") or source.get("nome_fantasia") or "Empresa Transportadora"

        return {
            "nome": str(nome).strip()[:150],
            "cnpj": raw_cnpj,
            "codigo": str(codigo).strip()[:20],
        }

    # --------------------------------------------------------------------------
    # MOTORISTA / CAMINHONEIRO
    # --------------------------------------------------------------------------
    @staticmethod
    def motorista_db1_to_db2(
        source: dict[str, Any],
        target_empresa_id: int | None,
        default_password_hash: str
    ) -> dict[str, Any]:
        """
        Converte Motorista do Banco 1 (DB1 / Instancia Operacional) para Banco 2 (DB2 / usuario com tipo 'motorista').
        Banco 2 espera: tipo, nome, cpf, email, telefone, data_nascimento, ativo, empresa_id, senha_hash, codigo_interno
        """
        raw_cpf = clean_cpf(source.get("cpf"))
        email = clean_email(source.get("email"))
        source_id = source.get("id")

        # Se o Banco 1 não possuir coluna de CPF, gera CPF derivado determinístico
        if not raw_cpf and source_id:
            raw_cpf = f"99{str(source_id).zfill(9)}"[:11]
        elif not raw_cpf:
            raw_cpf = "00000000000"

        codigo_interno = f"MOT-{str(source_id or raw_cpf[-4:]).zfill(4)}"

        return {
            "tipo": "motorista",
            "empresa_id": target_empresa_id,
            "nome": (source.get("nome") or "").strip()[:150],
            "cpf": raw_cpf,
            "codigo_interno": codigo_interno,
            "data_nascimento": source.get("data_nascimento"),
            "email": email or f"motorista_{raw_cpf}@efficientia.com.br",
            "telefone": source.get("telefone"),
            "senha_hash": source.get("senha") or default_password_hash,
            "ativo": True,
        }

    @staticmethod
    def motorista_db2_to_db1(
        source: dict[str, Any],
        target_empresa_id: int
    ) -> dict[str, Any]:
        """
        Converte Motorista do Banco 2 (DB2 / usuario) para Banco 1 (DB1 / Instancia Operacional motorista).
        Banco 1 espera: id_empresa, nome, data_nascimento, email, telefone, senha, assinatura
        """
        raw_cpf = clean_cpf(source.get("cpf"))
        email = clean_email(source.get("email"))

        return {
            "id_empresa": target_empresa_id,
            "nome": (source.get("nome") or "").strip()[:150],
            "data_nascimento": source.get("data_nascimento"),
            "email": email or (f"mot_{raw_cpf}@transportadora.com.br" if raw_cpf else None),
            "telefone": source.get("telefone") or "11999999999",
            "senha": source.get("senha_hash") or source.get("senha") or "senha123",
            "assinatura": source.get("url_assinatura_geral") or source.get("assinatura"),
            "cpf": raw_cpf if raw_cpf else None,
        }
    # --------------------------------------------------------------------------
    # DETECÇÃO DE DIVERGÊNCIAS
    # --------------------------------------------------------------------------
    @staticmethod
    def get_divergences(
        current_data: dict[str, Any],
        new_data: dict[str, Any],
        fields: list[str]
    ) -> dict[str, tuple[Any, Any]]:
        """
        Compara valores dos campos especificados.
        Retorna dicionário de diferenças: {campo: (valor_atual, novo_valor)}.
        """
        divergences: dict[str, tuple[Any, Any]] = {}
        for field in fields:
            if field not in new_data:
                continue
            cur_val = current_data.get(field)
            new_val = new_data.get(field)

            # Normalização de tipos para comparação segura
            if isinstance(cur_val, (date, datetime)) and isinstance(new_val, (date, datetime)):
                # Compara apenas a data se ambos forem datas
                cur_cmp = cur_val.strftime("%Y-%m-%d") if hasattr(cur_val, "strftime") else str(cur_val)
                new_cmp = new_val.strftime("%Y-%m-%d") if hasattr(new_val, "strftime") else str(new_val)
                if cur_cmp != new_cmp:
                    divergences[field] = (cur_val, new_val)
            elif cur_val is None and new_val is None:
                continue
            elif cur_val is None or new_val is None:
                # Se um for None e o outro string vazia, considera igual
                if (cur_val in (None, "") and new_val in (None, "")):
                    continue
                divergences[field] = (cur_val, new_val)
            else:
                # Comparação padrão por string limpa
                if str(cur_val).strip() != str(new_val).strip():
                    divergences[field] = (cur_val, new_val)

        return divergences
