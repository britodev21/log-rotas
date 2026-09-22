"""Autenticacao: login, renovacao de sessao, perfil e troca de senha."""

from __future__ import annotations

import math
from datetime import UTC, datetime

from fastapi import APIRouter, Request, status

from app.api.deps import AuthServiceDep, CurrentUser, DbSession
from app.core.errors import AuthenticationError, TooManyRequestsError
from app.core.senha import e_fraca
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginRequest, LoginResponse, RefreshRequest, TokenPair
from app.schemas.user import PasswordChange, UserRead
from app.services import seguranca_service as seg

router = APIRouter(prefix="/auth", tags=["Autenticacao"])


def ip_de(request: Request) -> str | None:
    """IP de quem chamou. Atras do nginx, o uvicorn precisa rodar com
    --proxy-headers para isto ser o IP do cliente, e nao o do proxy."""
    return request.client.host if request.client else None


@router.post("/login", response_model=LoginResponse, summary="Entrar no sistema")
def login(
    payload: LoginRequest,
    request: Request,
    auth: AuthServiceDep,
    session: DbSession,
) -> LoginResponse:
    """Entra no sistema, com limite de tentativas.

    Falhas seguidas bloqueiam a conta (e, em volume, o IP) por alguns
    minutos — **429** com `Retry-After`. Durante o bloqueio nem a senha certa
    entra. As regras e o porque de cada uma estao em docs/SEGURANCA.md.
    """
    ip = ip_de(request)
    agente = request.headers.get("user-agent")
    guarda = seg.SegurancaService(session)

    bloqueio = guarda.bloqueio(payload.email, ip)
    if bloqueio:
        guarda.registrar_tentativa(
            email=payload.email, ip=ip, motivo=seg.BLOQUEADO, user_agent=agente
        )
        session.commit()
        segundos = bloqueio.segundos_restantes(datetime.now(UTC))
        minutos = math.ceil(segundos / 60)
        # A mesma mensagem para conta e IP, e para conta que nao existe: o
        # bloqueio nao pode virar um jeito de descobrir quais contas existem.
        raise TooManyRequestsError(
            "Muitas tentativas de entrar. Por seguranca, o acesso ficou bloqueado "
            f"por alguns minutos. Tente de novo em {minutos} min.",
            segundos=segundos,
        )

    try:
        user = auth.authenticate(payload.email, payload.password)
    except AuthenticationError:
        conta = UserRepository(session).get_by_email(payload.email)
        motivo = seg.INATIVO if conta is not None and not conta.active else seg.CREDENCIAL
        guarda.registrar_tentativa(
            email=payload.email, ip=ip, motivo=motivo, user=conta, user_agent=agente
        )
        session.commit()
        raise

    guarda.registrar_tentativa(
        email=payload.email, ip=ip, motivo=seg.OK, user=user, user_agent=agente
    )
    tokens = auth.issue_tokens(user)
    # authenticate() pode ter atualizado o hash da senha (rehash do Argon2).
    session.commit()
    return LoginResponse(
        **tokens.model_dump(),
        user=UserRead.model_validate(user),
        senha_fraca=e_fraca(payload.password, email=user.email, nome=user.name),
    )


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
    request: Request,
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
    seg.SegurancaService(session).evento(
        "SENHA_TROCADA", actor=user, target=user, ip=ip_de(request)
    )
    session.commit()
    return auth.issue_tokens(user)
