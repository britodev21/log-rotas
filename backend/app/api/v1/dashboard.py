"""Painel operacional — o que está acontecendo hoje."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import AdminUser, DbSession
from app.core.enums import DeliveryStatus, RouteStatus
from app.models.base_location import BaseLocation
from app.models.delivery import Delivery
from app.models.route import Route
from app.schemas.planning import RotaRead

router = APIRouter(prefix="/painel", tags=["Painel"])


class IndicadoresEntregas(BaseModel):
    total: int
    pendentes: int
    planejadas: int
    em_rota: int
    entregues: int
    nao_entregues: int
    canceladas: int
    #: Entregas que ainda não podem ser planejadas. Fica em destaque porque
    #: é o problema que trava o planejamento do dia.
    sem_coordenada: int


class IndicadoresRotas(BaseModel):
    total: int
    planejadas: int
    em_andamento: int
    finalizadas: int
    motoristas_em_operacao: int
    distancia_planejada_m: int
    duracao_estimada_s: int


class PontoMapa(BaseModel):
    tipo: str
    id: int
    rotulo: str
    latitude: float
    longitude: float
    status: str | None = None


class PainelRead(BaseModel):
    data: date
    entregas: IndicadoresEntregas
    rotas: IndicadoresRotas
    #: Rotas em andamento, com paradas e geometria — o que o mapa desenha.
    rotas_ativas: list[RotaRead] = Field(default_factory=list)
    bases: list[PontoMapa] = Field(default_factory=list)
    entregas_no_mapa: list[PontoMapa] = Field(default_factory=list)


def _contar_entregas(session: Session, dia: date) -> IndicadoresEntregas:
    # `.all()` e obrigatorio: o Result do SQLAlchemy tem um metodo keys(),
    # entao dict() o trata como mapa e tenta indexa-lo, em vez de iterar os
    # pares. Sem isto, TypeError em tempo de execucao.
    por_status = dict(
        session.execute(
            select(Delivery.status, func.count())
            .where(Delivery.scheduled_date == dia)
            .group_by(Delivery.status)
        ).all()
    )

    sem_coordenada = session.scalar(
        select(func.count())
        .select_from(Delivery)
        .where(
            Delivery.scheduled_date == dia,
            Delivery.latitude.is_(None),
            Delivery.status.notin_(
                [DeliveryStatus.CANCELADA.value, DeliveryStatus.ENTREGUE.value]
            ),
        )
    )

    def q(*estados: DeliveryStatus) -> int:
        return sum(por_status.get(e.value, 0) for e in estados)

    return IndicadoresEntregas(
        total=sum(por_status.values()),
        pendentes=q(DeliveryStatus.PENDENTE),
        planejadas=q(DeliveryStatus.PLANEJADA),
        # CHEGOU conta como em rota: para quem olha o painel, o motorista
        # parado na porta do cliente ainda está na rua.
        em_rota=q(DeliveryStatus.EM_ROTA, DeliveryStatus.CHEGOU),
        entregues=q(DeliveryStatus.ENTREGUE),
        nao_entregues=q(DeliveryStatus.NAO_ENTREGUE),
        canceladas=q(DeliveryStatus.CANCELADA),
        sem_coordenada=sem_coordenada or 0,
    )


def _contar_rotas(session: Session, dia: date) -> IndicadoresRotas:
    rotas = list(
        session.scalars(
            select(Route).where(
                Route.date == dia,
                Route.status.in_(
                    [
                        RouteStatus.PLANEJADA.value,
                        RouteStatus.INICIADA.value,
                        RouteStatus.FINALIZADA.value,
                    ]
                ),
            )
        ).unique()
    )

    em_andamento = [r for r in rotas if r.status == RouteStatus.INICIADA.value]

    return IndicadoresRotas(
        total=len(rotas),
        planejadas=sum(1 for r in rotas if r.status == RouteStatus.PLANEJADA.value),
        em_andamento=len(em_andamento),
        finalizadas=sum(1 for r in rotas if r.status == RouteStatus.FINALIZADA.value),
        motoristas_em_operacao=len({r.driver_id for r in em_andamento if r.driver_id}),
        # Só as rotas confirmadas entram no total: rascunho é cenário, não
        # compromisso, e somá-lo inflaria o número do dia.
        distancia_planejada_m=sum(r.total_distance_m or 0 for r in rotas),
        duracao_estimada_s=sum(r.estimated_duration_s or 0 for r in rotas),
    )


@router.get("", response_model=PainelRead, summary="Visão geral do dia")
def painel(
    session: DbSession,
    _: AdminUser,
    data: Annotated[date | None, Query(description="Padrão: hoje.")] = None,
) -> PainelRead:
    """Indicadores operacionais e o que o mapa precisa desenhar.

    Uma chamada só: o painel atualiza por polling a cada poucos segundos, e
    quatro requisições por ciclo multiplicariam a carga sem nenhum ganho.

    Todos os números vêm do banco. Quando não há entregas cadastradas eles
    são zero de verdade — não há valor de exemplo em lugar nenhum.
    """
    dia = data or date.today()

    ativas = list(
        session.scalars(
            select(Route)
            .where(Route.date == dia, Route.status == RouteStatus.INICIADA.value)
            .order_by(Route.id)
        ).unique()
    )

    bases = [
        PontoMapa(
            tipo="base",
            id=b.id,
            rotulo=b.name,
            latitude=float(b.latitude),
            longitude=float(b.longitude),
        )
        for b in session.scalars(
            select(BaseLocation).where(
                BaseLocation.active.is_(True), BaseLocation.latitude.is_not(None)
            )
        ).unique()
    ]

    entregas_mapa = [
        PontoMapa(
            tipo="entrega",
            id=e.id,
            rotulo=e.recipient_name or e.address or f"Entrega {e.id}",
            latitude=float(e.latitude),
            longitude=float(e.longitude),
            status=e.status,
        )
        for e in session.scalars(
            select(Delivery)
            .where(Delivery.scheduled_date == dia, Delivery.latitude.is_not(None))
            .limit(500)
        ).unique()
    ]

    return PainelRead(
        data=dia,
        entregas=_contar_entregas(session, dia),
        rotas=_contar_rotas(session, dia),
        rotas_ativas=[RotaRead.model_validate(r) for r in ativas],
        bases=bases,
        entregas_no_mapa=entregas_mapa,
    )
