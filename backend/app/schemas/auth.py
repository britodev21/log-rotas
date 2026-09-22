"""Schemas de autenticacao."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import Email
from app.schemas.user import UserRead


class LoginRequest(BaseModel):
    email: Email
    # Sem min_length aqui de proposito: no login validamos a credencial, nao a
    # politica de senha. Exigir tamanho minimo no login apenas informaria a um
    # atacante que senhas curtas nao existem no sistema.
    password: str = Field(max_length=128)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Validade do access token, em segundos.")


class LoginResponse(TokenPair):
    user: UserRead
    #: A senha usada deixaria de passar na politica de hoje (lista de senhas
    #: conhecidas, nome no meio...). Ela continua entrando — trancar alguem
    #: fora por uma regra nova seria pior —, mas a tela pede a troca.
    senha_fraca: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str
