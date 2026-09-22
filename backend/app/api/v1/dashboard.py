"""Painel operacional — o que está acontecendo hoje."""

from __future__ import annotations

from datetime import UTC, date, datetime
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
from app.routing import transito
from app.schemas.planning import RotaRead
from app.schemas.rastreamento import (
    AoVivoRead,
    PosicaoRead,
    PrevisaoParadaRead,
    PrevisaoRead,
    RotaAoVivoRead,
)
from app.services.execution_service import progresso
from app.services.rastreamento import RastreamentoService

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


def _numero(valor) -> float | None:
    return float(valor) if valor is not None else None


@router.get("/ao-vivo", response_model=AoVivoRead, summary="Caminhoes em rota agora")
def ao_vivo(session: DbSession, _: AdminUser) -> AoVivoRead:
    """Onde cada caminhao em rota esta e quando chega em cada parada.

    Separado do painel porque o ritmo e outro: o painel muda a cada poucos
    minutos, o caminhao a cada poucos segundos. A tela consulta isto com
    mais frequencia sem recarregar os indicadores do dia.

    A previsao nao e recalculada a cada consulta — ha uma memoria de ate
    45 s por rota (ver app/services/rastreamento.py). Recalcular a cada 5 s
    martelaria o servico de rotas e, com transito ligado, a conta do Google.
    """
    servico = RastreamentoService(session)
    agora = datetime.now(UTC)
    rotas = []
    for rota in servico.rotas_em_andamento():
        ultima = servico.ultima(rota.id)
        rastro = servico.rastro(rota.id)
        previsao = servico.previsao(rota, ultima)
        andamento = progresso(rota)
        proxima = previsao.proxima
        rotas.append(
            RotaAoVivoRead(
                rota_id=rota.id,
                motorista=rota.driver.name if rota.driver else None,
                veiculo=rota.vehicle.name if rota.vehicle else None,
                placa=rota.vehicle.plate if rota.vehicle else None,
                situacao=servico.situacao(rota, ultima, agora, rastro),
                posicao=PosicaoRead(
                    latitude=float(ultima.latitude),
                    longitude=float(ultima.longitude),
                    precisao_m=_numero(ultima.accuracy_m),
                    velocidade_mps=_numero(ultima.speed_mps),
                    direcao_graus=_numero(ultima.heading_deg),
                    registrada_em=ultima.recorded_at,
                    recebida_em=ultima.received_at,
                )
                if ultima
                else None,
                idade_s=int((agora - ultima.recorded_at).total_seconds()) if ultima else None,
                rastro=[[float(p.latitude), float(p.longitude)] for p in rastro],
                proxima=PrevisaoParadaRead.model_validate(proxima, from_attributes=True)
                if proxima
                else None,
                feitas=andamento["concluidas"],
                total=andamento["total"],
                previsao=PrevisaoRead.model_validate(previsao, from_attributes=True),
            )
        )
    return AoVivoRead(rotas=rotas, transito_configurado=transito.disponivel(), gerado_em=agora)
