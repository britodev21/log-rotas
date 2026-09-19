"""Autenticacao: login, renovacao de sessao, perfil e troca de senha."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import AuthServiceDep, CurrentUser, DbSession
from app.schemas.auth import LoginRequest, LoginResponse, RefreshRequest, TokenPair
from app.schemas.user import PasswordChange, UserRead

router = APIRouter(prefix="/auth", tags=["Autenticacao"])


@router.post("/login", response_model=LoginResponse, summary="Entrar no sistema")
def login(payload: LoginRequest, auth: AuthServiceDep, session: DbSession) -> LoginResponse:
    user = auth.authenticate(payload.email, payload.password)
    tokens = auth.issue_tokens(user)
    # authenticate() pode ter atualizado o hash da senha (rehash do Argon2).
    session.commit()
    return LoginResponse(**tokens.model_dump(), user=UserRead.model_validate(user))


@router.post("/refresh", response_model=TokenPair, summary="Renovar a sessao")
def refresh(payload: RefreshRequest, auth: AuthServiceDep) -> TokenPair:
    _, tokens = auth.refresh(payload.refresh_token)
    return tokens


@router.get("/me", response_model=UserRead, summary="Dados do usuario autenticado")
def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.post(
    "/senha",
    response_model=TokenPair,
    status_code=status.HTTP_200_OK,
    summary="Trocar a propria senha",
)
def change_password(
    payload: PasswordChange,
    user: CurrentUser,
    auth: AuthServiceDep,
    session: DbSession,
) -> TokenPair:
    """Troca a senha e devolve um par de tokens novo.

    A troca invalida as sessoes anteriores (incrementa token_version), entao
    quem trocou precisa receber tokens novos para nao ser deslogado do proprio
    navegador enquanto as outras sessoes caem.
    """
    auth.change_password(user, payload.current_password, payload.new_password)
    session.commit()
    return auth.issue_tokens(user)
