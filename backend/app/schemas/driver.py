"""Schemas da operacao do motorista."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.core.enums import FailureReason, RouteStatus
from app.schemas.common import Observacao, ORMModel, TextoOpcional
from app.schemas.planning import ParadaRead, VeiculoResumo


class Coordenada(BaseModel):
    """Onde o motorista estava ao registrar.

    Opcional de proposito: o navegador so libera geolocalizacao em contexto
    seguro (HTTPS), e nem sempre ha sinal. Exigir travaria o motorista na
    calcada. Ver docs/LIMITACOES.md.
    """

    latitude: Annotated[float | None, Field(ge=-90, le=90)] = None
    longitude: Annotated[float | None, Field(ge=-180, le=180)] = None


class ChegadaRequest(Coordenada):
    pass


class EntregaRealizadaRequest(Coordenada):
    recebedor: TextoOpcional = None
    observacao: Observacao = None


class InsucessoRequest(Coordenada):
    motivo: FailureReason
    observacao: Observacao = None


class Progresso(BaseModel):
    total: int
    concluidas: int
    restantes: int
    percentual: int


class BaseResumo(ORMModel):
    id: int
    name: str
    address: str | None
    latitude: float | None
    longitude: float | None


class RotaMotoristaRead(ORMModel):
    id: int
    date: date
    status: RouteStatus
    sequence_in_day: int
    total_distance_m: int | None
    estimated_duration_s: int | None
    started_at: datetime | None
    finished_at: datetime | None
    geometry: str | None
    vehicle: VeiculoResumo | None
    base: BaseResumo | None
    stops: list[ParadaRead] = Field(default_factory=list)
    progresso: Progresso | None = None
