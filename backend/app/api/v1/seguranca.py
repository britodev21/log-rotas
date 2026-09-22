"""Segurança: a política em vigor, contas bloqueadas e o registro de eventos.

Somente `ADMIN`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession
from app.api.v1.auth import ip_de
from app.core.config import get_settings
from app.core.senha import CARACTERES_DISTINTOS_MINIMOS, SENHA_MINIMA
from app.models.user import User
from app.services.seguranca_service import SegurancaService

router = APIRouter(prefix="/seguranca", tags=["Seguranca"])


class PoliticaRead(BaseModel):
    """O que está em vigor, lido da configuração — nunca um texto fixo que
    pode divergir do que o servidor de fato faz."""

    senha_minima: int
    senha_caracteres_distintos: int
    login_max_falhas_conta: int
    login_max_falhas_ip: int
    login_janela_minutos: int
    login_bloqueio_minutos: int
    sessao_minutos: int
    renovacao_dias: int
    hsts: bool
    retencao_posicoes_dias: int
    retencao_tentativas_login_dias: int
    retencao_eventos_seguranca_dias: int


class ContaBloqueadaRead(BaseModel):
    email: str
    ate: datetime
    falhas: int
    nome: str | None = None


class DesbloqueioRequest(BaseModel):
    email: EmailStr


class EventoRead(BaseModel):
    id: int
    tipo: str
    quando: datetime
    email: str | None
    ip: str | None
    detalhe: dict
    quem: str | None
    sobre: str | None


@router.get("/politica", response_model=PoliticaRead, summary="Política em vigor")
def politica(_: AdminUser) -> PoliticaRead:
    c = get_settings()
    return PoliticaRead(
        senha_minima=SENHA_MINIMA,
        senha_caracteres_distintos=CARACTERES_DISTINTOS_MINIMOS,
        login_max_falhas_conta=c.login_max_falhas_conta,
        login_max_falhas_ip=c.login_max_falhas_ip,
        login_janela_minutos=c.login_janela_minutos,
        login_bloqueio_minutos=c.login_bloqueio_minutos,
        sessao_minutos=c.access_token_expire_minutes,
        renovacao_dias=c.refresh_token_expire_days,
        hsts=c.hsts,
        retencao_posicoes_dias=c.retencao_posicoes_dias,
        retencao_tentativas_login_dias=c.retencao_tentativas_login_dias,
        retencao_eventos_seguranca_dias=c.retencao_eventos_seguranca_dias,
    )


@router.get("/bloqueios", response_model=list[ContaBloqueadaRead], summary="Contas bloqueadas")
def bloqueios(session: DbSession, _: AdminUser) -> list[ContaBloqueadaRead]:
    """Contas bloqueadas agora por tentativas de login.

    Inclui e-mail sem conta: alguém tentando entrar com ele é informação
    para quem administra, mesmo que a conta não exista.
    """
    lista = SegurancaService(session).contas_bloqueadas()
    nomes = dict(
        session.execute(
            select(User.email, User.name).where(User.email.in_([b.email for b in lista]))
        ).all()
    ) if lista else {}
    return [
        ContaBloqueadaRead(email=b.email, ate=b.ate, falhas=b.falhas, nome=nomes.get(b.email))
        for b in lista
    ]


@router.post(
    "/bloqueios/desbloquear",
    response_model=list[ContaBloqueadaRead],
    summary="Desbloquear uma conta",
)
def desbloquear(
    payload: DesbloqueioRequest, request: Request, session: DbSession, admin: AdminUser
) -> list[ContaBloqueadaRead]:
    """Libera a conta antes de o bloqueio vencer — o motorista que errou a
    senha e ligou pedindo ajuda. Fica registrado quem liberou."""
    SegurancaService(session).desbloquear(payload.email, actor=admin, ip=ip_de(request))
    session.commit()
    return bloqueios(session, admin)


@router.get("/eventos", response_model=list[EventoRead], summary="Eventos de segurança")
def eventos(
    session: DbSession,
    _: AdminUser,
    limite: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[EventoRead]:
    lista = SegurancaService(session).eventos(limite)
    ids = {i for e in lista for i in (e.actor_id, e.target_id) if i}
    nomes = (
        dict(session.execute(select(User.id, User.name).where(User.id.in_(ids))).all())
        if ids
        else {}
    )
    return [
        EventoRead(
            id=e.id,
            tipo=e.tipo,
            quando=e.created_at,
            email=e.email,
            ip=e.ip,
            detalhe=e.detalhe or {},
            quem=nomes.get(e.actor_id),
            sobre=nomes.get(e.target_id),
        )
        for e in lista
    ]
