"""Tipos e validadores compartilhados pelos schemas Pydantic."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

SENHA_MINIMA = 10

# Placa brasileira: formato antigo AAA1234 e Mercosul AAA1A23.
_PLACA = re.compile(r"^[A-Z]{3}[0-9][0-9A-Z][0-9]{2}$")


class ORMModel(BaseModel):
    """Base dos schemas de saida, que leem direto dos modelos SQLAlchemy."""

    model_config = ConfigDict(from_attributes=True)


def _normalizar_email(valor: str) -> str:
    # Login nao diferencia maiusculas de minusculas. A normalizacao acontece
    # aqui, na borda, e a CHECK constraint em users garante o resto.
    return valor.strip().lower()


def _limpar(valor: str | None) -> str | None:
    """Espaco nas pontas vira None, para o banco nao guardar string vazia.

    Sem isso o campo opcional passa a ter dois estados que significam a mesma
    coisa — NULL e "" — e toda consulta precisa tratar os dois.
    """
    if valor is None:
        return None
    limpo = " ".join(valor.split())
    return limpo or None


def _normalizar_placa(valor: str) -> str:
    bruto = re.sub(r"[^A-Za-z0-9]", "", valor).upper()
    if not _PLACA.match(bruto):
        raise ValueError(
            "Placa invalida. Use o formato ABC1234 (antigo) ou ABC1D23 (Mercosul)."
        )
    return bruto


def _somente_digitos(valor: str | None) -> str | None:
    """Telefone e documento guardados so com digitos.

    A mascara e assunto de exibicao. Guardar "(67) 99999-0000" e "67999990000"
    como se fossem valores diferentes torna qualquer busca ou comparacao
    pouco confiavel.
    """
    if valor is None:
        return None
    digitos = re.sub(r"\D", "", valor)
    return digitos or None


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
NomeCurto = Annotated[str, Field(min_length=2, max_length=80)]
NomeLongo = Annotated[str, Field(min_length=2, max_length=160)]

Placa = Annotated[str, AfterValidator(_normalizar_placa)]
Telefone = Annotated[str | None, Field(max_length=30), AfterValidator(_somente_digitos)]
Documento = Annotated[str | None, Field(max_length=20), AfterValidator(_somente_digitos)]
Endereco = Annotated[str | None, Field(max_length=255), AfterValidator(_limpar)]
Cep = Annotated[str | None, Field(max_length=9), AfterValidator(_somente_digitos)]
Observacao = Annotated[str | None, Field(max_length=500), AfterValidator(_limpar)]
TextoOpcional = Annotated[str | None, Field(max_length=160), AfterValidator(_limpar)]

Latitude = Annotated[float | None, Field(ge=-90, le=90)]
Longitude = Annotated[float | None, Field(ge=-180, le=180)]
