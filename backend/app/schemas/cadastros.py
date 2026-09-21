"""Schemas dos cadastros: bases, veiculos, motoristas e clientes.

Os quatro moram no mesmo arquivo porque compartilham o mesmo formato e sao
lidos juntos. Quando entregas chegarem (com regras bem maiores), elas terao
arquivo proprio.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from app.core.enums import GeocodePrecision, GeocodeStatus
from app.schemas.common import (
    Cep,
    Documento,
    Endereco,
    Latitude,
    Longitude,
    NomeCurto,
    NomeLongo,
    NomePessoa,
    Observacao,
    ORMModel,
    Placa,
    Telefone,
    TextoOpcional,
)


class GeocodeRead(ORMModel):
    """Bloco de geocodificacao devolvido junto de quem tem endereco."""

    address: str | None
    postal_code: str | None
    latitude: float | None
    longitude: float | None
    geocode_status: GeocodeStatus
    geocode_precision: GeocodePrecision | None
    geocoded_at: datetime | None


# --------------------------------------------------------------------------- #
# Bases
# --------------------------------------------------------------------------- #
class BaseLocationCreate(BaseModel):
    name: NomeCurto
    address: Endereco = None
    postal_code: Cep = None
    phone: Telefone = None
    latitude: Latitude = None
    longitude: Longitude = None
    #: True somente quando uma pessoa marcou o ponto no mapa — clicou,
    #: arrastou o pino ou escolheu um candidato conferindo onde caiu.
    #: O pino que o formulario busca sozinho NAO conta: em Campo Grande o
    #: geocodificador gratuito resolve no nivel da rua quase sempre, e
    #: aceitar esse palpite como confirmado foi o defeito que permitia uma
    #: entrega ser planejada para um ponto qualquer da avenida.
    #: Ver app/services/precisao.py.
    ponto_confirmado: bool = False
    is_default: bool = False
    active: bool = True
    notes: Observacao = None

    @model_validator(mode="after")
    def _coordenada_completa(self):
        # Uma coordenada pela metade nao localiza nada, e o banco recusaria.
        # Barrar aqui devolve 422 com explicacao, em vez de 409 generico.
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Informe latitude e longitude juntas, ou nenhuma das duas.")
        return self


class BaseLocationUpdate(BaseModel):
    name: NomeCurto | None = None
    address: Endereco = None
    postal_code: Cep = None
    phone: Telefone = None
    latitude: Latitude = None
    longitude: Longitude = None
    #: True somente quando uma pessoa marcou o ponto no mapa — clicou,
    #: arrastou o pino ou escolheu um candidato conferindo onde caiu.
    #: O pino que o formulario busca sozinho NAO conta: em Campo Grande o
    #: geocodificador gratuito resolve no nivel da rua quase sempre, e
    #: aceitar esse palpite como confirmado foi o defeito que permitia uma
    #: entrega ser planejada para um ponto qualquer da avenida.
    #: Ver app/services/precisao.py.
    ponto_confirmado: bool = False
    is_default: bool | None = None
    active: bool | None = None
    notes: Observacao = None


class BaseLocationRead(GeocodeRead):
    id: int
    name: str
    phone: str | None
    is_default: bool
    active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Veiculos
# --------------------------------------------------------------------------- #
Capacidade = Annotated[Decimal | None, Field(gt=0, le=Decimal("999999"))]


class VehicleCreate(BaseModel):
    name: NomeCurto
    plate: Placa
    model: TextoOpcional = None
    # Todas as capacidades sao opcionais: ainda nao se sabe qual delas limita
    # a operacao da Britto. Ver docs/LIMITACOES.md.
    capacity_weight_kg: Capacidade = None
    capacity_volume_m3: Capacidade = None
    capacity_length_m: Capacidade = None
    max_stops: Annotated[int | None, Field(gt=0, le=500)] = None
    crew_size: Annotated[int, Field(ge=1, le=20)] = 1
    active: bool = True
    notes: Observacao = None


class VehicleUpdate(BaseModel):
    name: NomeCurto | None = None
    plate: Placa | None = None
    model: TextoOpcional = None
    capacity_weight_kg: Capacidade = None
    capacity_volume_m3: Capacidade = None
    capacity_length_m: Capacidade = None
    max_stops: Annotated[int | None, Field(gt=0, le=500)] = None
    crew_size: Annotated[int | None, Field(ge=1, le=20)] = None
    active: bool | None = None
    notes: Observacao = None


class VehicleRead(ORMModel):
    id: int
    name: str
    plate: str
    model: str | None
    capacity_weight_kg: Decimal | None
    capacity_volume_m3: Decimal | None
    capacity_length_m: Decimal | None
    max_stops: int | None
    crew_size: int
    active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Motoristas
# --------------------------------------------------------------------------- #
class DriverCreate(BaseModel):
    name: NomePessoa
    # Anulavel: motorista pode existir sem acesso ao sistema.
    user_id: int | None = None
    phone: Telefone = None
    document: Documento = None
    license_number: TextoOpcional = None
    license_expires_at: date | None = None
    active: bool = True
    notes: Observacao = None


class DriverUpdate(BaseModel):
    name: NomePessoa | None = None
    user_id: int | None = None
    phone: Telefone = None
    document: Documento = None
    license_number: TextoOpcional = None
    license_expires_at: date | None = None
    active: bool | None = None
    notes: Observacao = None


class DriverUsuarioRead(ORMModel):
    id: int
    name: str
    email: str
    active: bool


class DriverRead(ORMModel):
    id: int
    name: str
    user_id: int | None
    user: DriverUsuarioRead | None
    phone: str | None
    document: str | None
    license_number: str | None
    license_expires_at: date | None
    active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Clientes
# --------------------------------------------------------------------------- #
class CustomerCreate(BaseModel):
    name: NomeLongo
    phone: Telefone = None
    email: TextoOpcional = None
    document: Documento = None
    address: Endereco = None
    postal_code: Cep = None
    latitude: Latitude = None
    longitude: Longitude = None
    #: True so quando uma pessoa marcou o ponto no mapa. O pino que o
    #: formulario acha sozinho nao conta — ver app/schemas/delivery.py e
    #: app/services/precisao.py.
    ponto_confirmado: bool = False
    active: bool = True
    notes: Observacao = None

    @model_validator(mode="after")
    def _coordenada_completa(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Informe latitude e longitude juntas, ou nenhuma das duas.")
        return self


class CustomerUpdate(BaseModel):
    name: NomeLongo | None = None
    phone: Telefone = None
    email: TextoOpcional = None
    document: Documento = None
    address: Endereco = None
    postal_code: Cep = None
    latitude: Latitude = None
    longitude: Longitude = None
    #: True so quando uma pessoa marcou o ponto no mapa. O pino que o
    #: formulario acha sozinho nao conta — ver app/schemas/delivery.py e
    #: app/services/precisao.py.
    ponto_confirmado: bool = False
    active: bool | None = None
    notes: Observacao = None


class CustomerRead(GeocodeRead):
    id: int
    name: str
    phone: str | None
    email: str | None
    document: str | None
    active: bool
    notes: str | None
    created_at: datetime
    updated_at: datetime
