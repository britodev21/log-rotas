"""Gestao de usuarios — exclusiva do administrador."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, DbSession
from app.core.enums import Role
from app.schemas.user import PasswordReset, UserCreate, UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.get("", response_model=list[UserRead], summary="Listar usuarios")
def list_users(
    session: DbSession,
    _: AdminUser,
    role: Annotated[Role | None, Query(description="Filtrar por papel.")] = None,
    active: Annotated[bool | None, Query(description="Filtrar por situacao.")] = None,
    search: Annotated[str | None, Query(description="Busca por nome ou e-mail.")] = None,
) -> list[UserRead]:
    usuarios = UserService(session).list(role=role, active=active, search=search)
    return [UserRead.model_validate(u) for u in usuarios]


@router.post(
    "",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar usuario",
)
def create_user(payload: UserCreate, session: DbSession, admin: AdminUser) -> UserRead:
    return UserRead.model_validate(UserService(session).create(payload, actor=admin))


@router.get("/{user_id}", response_model=UserRead, summary="Detalhe do usuario")
def get_user(user_id: int, session: DbSession, _: AdminUser) -> UserRead:
    return UserRead.model_validate(UserService(session).get(user_id))


@router.patch("/{user_id}", response_model=UserRead, summary="Alterar usuario")
def update_user(
    user_id: int, payload: UserUpdate, session: DbSession, admin: AdminUser
) -> UserRead:
    return UserRead.model_validate(UserService(session).update(user_id, payload, actor=admin))


@router.post(
    "/{user_id}/senha", response_model=UserRead, summary="Redefinir a senha de um usuario"
)
def reset_password(
    user_id: int, payload: PasswordReset, session: DbSession, admin: AdminUser
) -> UserRead:
    """Usado quando o motorista esquece a senha.

    Nao exige a senha atual, derruba as sessoes abertas do usuario e nao
    devolve a senha nova em lugar nenhum — o admin a informa pessoalmente.
    """
    user = UserService(session).reset_password(user_id, payload.new_password, actor=admin)
    return UserRead.model_validate(user)
