"""Manutenção: a limpeza automática, o que ela guarda e quando rodou.

Somente `ADMIN`.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import AdminUser, DbSession
from app.core.config import get_settings
from app.core.errors import ConflictError
from app.services import manutencao

router = APIRouter(prefix="/manutencao", tags=["Manutencao"])


class ExecucaoRead(BaseModel):
    id: int
    origem: str
    iniciada_em: datetime
    terminada_em: datetime | None
    resultado: dict
    erro: str | None


class ManutencaoRead(BaseModel):
    #: Hora local em que a limpeza roda sozinha; nulo quando desligada.
    hora_agendada: int | None
    retencao_posicoes_dias: int
    retencao_tentativas_login_dias: int
    retencao_eventos_seguranca_dias: int
    retencao_cache_falhas_dias: int
    ultimas: list[ExecucaoRead]


def _ler(session) -> ManutencaoRead:
    c = get_settings()
    return ManutencaoRead(
        hora_agendada=c.limpeza_hora if c.limpeza_hora >= 0 else None,
        retencao_posicoes_dias=c.retencao_posicoes_dias,
        retencao_tentativas_login_dias=c.retencao_tentativas_login_dias,
        retencao_eventos_seguranca_dias=c.retencao_eventos_seguranca_dias,
        retencao_cache_falhas_dias=manutencao.RETENCAO_CACHE_FALHAS_DIAS,
        ultimas=[ExecucaoRead.model_validate(e, from_attributes=True)
                 for e in manutencao.ultimas(session)],
    )


@router.get("", response_model=ManutencaoRead, summary="Limpeza automatica")
def ler(session: DbSession, _: AdminUser) -> ManutencaoRead:
    return _ler(session)


@router.post("/limpar", response_model=ManutencaoRead, summary="Limpar agora")
def limpar_agora(session: DbSession, admin: AdminUser) -> ManutencaoRead:
    """Roda a limpeza sem esperar o horário. Fica registrado quem pediu."""
    if manutencao.limpar(session, origem=manutencao.MANUAL, actor=admin) is None:
        raise ConflictError("Outra limpeza esta em andamento. Tente de novo em instantes.")
    return _ler(session)
