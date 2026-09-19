"""Schemas do primeiro acesso.

O Log Rotas nao tem auto-cadastro publico: e a aplicacao de uma empresa so.
Na primeira execucao, enquanto nao existir nenhum usuario, esta rota cria a
empresa e o administrador inicial. Depois disso ela se fecha para sempre.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Email, NomePessoa, Senha


class SetupStatus(BaseModel):
    needs_setup: bool = Field(
        description="True enquanto nao existir nenhum usuario no sistema."
    )


class SetupRequest(BaseModel):
    company_name: str = Field(min_length=2, max_length=160)
    admin_name: NomePessoa
    admin_email: Email
    admin_password: Senha
