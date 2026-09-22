"""Schemas do planejamento de rotas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from app.core.enums import MatrixSource, PlanStatus, RouteStatus, StopStatus, StopType
from app.schemas.common import ORMModel


class CalcularRequest(BaseModel):
    """Entrada do planejador."""

    date: date
    base_id: int
    #: Entregas escolhidas. Vazio = todas as PENDENTES da data.
    delivery_ids: list[int] = Field(default_factory=list)
    vehicle_ids: list[int] = Field(min_length=1)
    #: Motoristas, na ordem de preferencia. Podem ser menos que os veiculos:
    #: rota sem motorista fica pendente de atribuicao, o que e melhor do que
    #: recusar o calculo inteiro.
    driver_ids: list[int] = Field(default_factory=list)

    limite_tempo_s: Annotated[int, Field(ge=1, le=120)] = 10
    inicio_turno: Annotated[str, Field(pattern=r"^\d{2}:\d{2}$")] = "08:00"
    permitir_dispensar: bool = True
    #: Tempo de deslocamento com o transito previsto (Google) em vez da rua
    #: livre. Sem efeito quando o servidor nao tem transito configurado.
    considerar_transito: bool = True
    #: Quantas vezes cada veiculo pode sair da base no dia. Com 2 ou mais, ele
    #: volta para recarregar quando a carga do dia nao cabe de uma vez.
    max_viagens: Annotated[int, Field(ge=1, le=4)] = 1
    #: Minutos parado na base entre uma viagem e a proxima.
    recarga_min: Annotated[int, Field(ge=0, le=240)] = 30


class EntregaNaParada(ORMModel):
    id: int
    delivery_id: int
    sequence_in_stop: int
    status: str
    delivered_at: datetime | None
    failure_reason: str | None
    receiver_name: str | None


class ParadaRead(ORMModel):
    id: int
    stop_type: StopType
    trip_number: int
    sequence: int
    label: str | None
    address: str | None
    latitude: float | None
    longitude: float | None
    estimated_arrival: datetime | None
    distance_from_previous_m: int | None
    duration_from_previous_s: int | None
    service_time_s: int | None
    arrived_at: datetime | None
    departed_at: datetime | None
    status: StopStatus
    items: list[EntregaNaParada] = Field(default_factory=list)


class VeiculoResumo(ORMModel):
    id: int
    name: str
    plate: str


class MotoristaResumo(ORMModel):
    id: int
    name: str


class RotaRead(ORMModel):
    id: int
    route_plan_id: int | None
    base_id: int
    vehicle_id: int
    driver_id: int | None
    vehicle: VeiculoResumo | None
    driver: MotoristaResumo | None
    date: date
    status: RouteStatus
    sequence_in_day: int
    total_distance_m: int | None
    estimated_duration_s: int | None
    planned_weight_kg: Decimal | None
    planned_volume_m3: Decimal | None
    started_at: datetime | None
    finished_at: datetime | None
    geometry: str | None
    stops: list[ParadaRead] = Field(default_factory=list)


class DispensadaRead(BaseModel):
    delivery_ids: list[int]
    rotulo: str
    motivo: str


class PlanoRead(ORMModel):
    id: int
    base_id: int
    date: date
    status: PlanStatus
    matrix_source: MatrixSource
    #: True quando as distancias sao estimativa em linha reta, nao medicao
    #: na malha viaria. A interface e obrigada a mostrar isso.
    distancias_estimadas: bool = False
    solver: str | None
    solver_status: str | None
    solver_time_ms: int | None
    total_distance_m: int | None
    total_duration_s: int | None
    unassigned: list = Field(default_factory=list)
    avisos: list[str] = Field(default_factory=list)
    #: Como o transito entrou no calculo: `considerado`, e ou o `motivo` de
    #: nao ter entrado, ou `partida`, `consultas`, pares medidos e por fator,
    #: `fator`, e o deslocamento das rotas com e sem transito.
    transito: dict | None = None
    confirmed_at: datetime | None
    created_at: datetime
    routes: list[RotaRead] = Field(default_factory=list)


class PlanoResumo(ORMModel):
    id: int
    date: date
    status: PlanStatus
    matrix_source: MatrixSource
    total_distance_m: int | None
    total_duration_s: int | None
    created_at: datetime
    confirmed_at: datetime | None


class ConfirmarRequest(BaseModel):
    """Atribuicao final de motorista a cada rota, feita na revisao."""

    atribuicoes: dict[int, int] = Field(
        default_factory=dict,
        description="Mapa rota_id -> motorista_id. Sobrescreve a sugestao do calculo.",
    )
