"""Schemas de geocodificacao."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.core.enums import GeocodePrecision, GeocodeStatus

TipoAlvo = Literal["entrega", "cliente", "base"]


class CoordenadaManual(BaseModel):
    """Pino ajustado a mao pelo administrador."""

    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]


class CandidatoRead(BaseModel):
    latitude: float
    longitude: float
    display_name: str
    precision: GeocodePrecision | None


class GeocodeTentativaRead(BaseModel):
    status: str
    latitude: float | None = None
    longitude: float | None = None
    precision: GeocodePrecision | None = None
    normalized_address: str | None = None
    provider: str
    error: str | None = None
    candidatos: list[CandidatoRead] = []


class LoteRequest(BaseModel):
    tipo: TipoAlvo = "entrega"
    limite: Annotated[int, Field(ge=1, le=200)] = 50
    forcar: bool = False


class LoteResultado(BaseModel):
    processados: int
    ok: int
    ambiguo: int
    falhou: int
    manual: int
    erro_provedor: int


class PendenteRead(BaseModel):
    tipo: TipoAlvo
    id: int
    titulo: str
    address: str | None
    geocode_status: GeocodeStatus
    geocode_error: str | None
    latitude: float | None
    longitude: float | None
