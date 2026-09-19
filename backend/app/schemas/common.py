"""Tipos e validadores compartilhados pelos schemas Pydantic."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

SENHA_MINIMA = 10


class ORMModel(BaseModel):
    """Base dos schemas de saida, que leem direto dos modelos SQLAlchemy."""

    model_config = ConfigDict(from_attributes=True)


def _normalizar_email(valor: str) -> str:
    # Login nao diferencia maiusculas de minusculas. A normalizacao acontece
    # aqui, na borda, e a CHECK constraint em users garante o resto.
    return valor.strip().lower()


Email = Annotated[EmailStr, AfterValidator(_normalizar_email)]

Senha = Annotated[
    str,
    Field(
        min_length=SENHA_MINIMA,
        max_length=128,
        description=f"Minimo de {SENHA_MINIMA} caracteres.",
    ),
]

NomePessoa = Annotated[str, Field(min_length=2, max_length=120)]
