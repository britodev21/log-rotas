"""Primeiro acesso — rotas publicas, disponiveis apenas com o sistema vazio."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import AuthServiceDep, DbSession
from app.schemas.auth import LoginResponse
from app.schemas.setup import SetupRequest, SetupStatus
from app.schemas.user import UserRead
from app.services.setup_service import SetupService

router = APIRouter(prefix="/setup", tags=["Primeiro acesso"])


@router.get("/status", response_model=SetupStatus, summary="O sistema ja foi configurado?")
def setup_status(session: DbSession) -> SetupStatus:
    """Consultada pelo frontend antes de mostrar a tela de login.

    Enquanto nao existir usuario, o frontend leva direto para o primeiro acesso
    em vez de apresentar um login que ninguem conseguiria usar.
    """
    return SetupStatus(needs_setup=SetupService(session).needs_setup())


@router.post(
    "",
    response_model=LoginResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Criar a empresa e o administrador inicial",
)
def run_setup(payload: SetupRequest, session: DbSession, auth: AuthServiceDep) -> LoginResponse:
    """Cria empresa + primeiro ADMIN e ja devolve a sessao autenticada.

    Responde 409 se o sistema ja tiver qualquer usuario — dai em diante o
    cadastro de usuarios passa a ser exclusividade do administrador.
    """
    admin = SetupService(session).run(payload)
    tokens = auth.issue_tokens(admin)
    return LoginResponse(**tokens.model_dump(), user=UserRead.model_validate(admin))
