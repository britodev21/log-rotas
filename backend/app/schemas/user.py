"""Schemas de usuario."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import Role
from app.schemas.common import Email, NomePessoa, ORMModel, Senha


class UserCreate(BaseModel):
    name: NomePessoa
    email: Email
    password: Senha
    role: Role
    active: bool = True


class UserUpdate(BaseModel):
    name: NomePessoa | None = None
    role: Role | None = None
    active: bool | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: Senha


class PasswordReset(BaseModel):
    """Redefinicao feita por um ADMIN, sem exigir a senha atual."""

    new_password: Senha


class UserRead(ORMModel):
    id: int
    name: str
    email: str
    role: Role
    active: bool
    email_verified: bool
    created_at: datetime
    updated_at: datetime
