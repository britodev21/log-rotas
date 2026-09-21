"""Schemas de entrega."""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from app.core.enums import DeliveryStatus, FailureReason, Priority
from app.schemas.cadastros import GeocodeRead
from app.schemas.common import (
    Cep,
    Endereco,
    Latitude,
    Longitude,
    Observacao,
    Telefone,
    TextoOpcional,
)

Medida = Annotated[Decimal | None, Field(ge=0, le=Decimal("999999"))]
Equipe = Annotated[int, Field(ge=1, le=20)]
TempoServico = Annotated[int | None, Field(gt=0, le=1440)]


class _DeliveryBase(BaseModel):
    customer_id: int | None = None
    order_number: TextoOpcional = None
    invoice_number: TextoOpcional = None

    recipient_name: TextoOpcional = None
    recipient_phone: Telefone = None

    description: Endereco = None
    address: Endereco = None
    postal_code: Cep = None
    latitude: Latitude = None
    longitude: Longitude = None
    #: True somente quando uma pessoa marcou o ponto no mapa — clicou,
    #: arrastou o pino ou escolheu um candidato conferindo onde caiu.
    #: O pino que o formulario busca sozinho NAO conta: em Campo Grande o
    #: OpenStreetMap tem numero de porta em cerca de 530 predios, e o
    #: geocodificador resolve no nivel da rua quase sempre. Aceitar esse
    #: palpite como confirmado foi o defeito que deixava uma entrega ser
    #: planejada para um ponto qualquer de uma avenida de 10 km.
    #: A barreira esta em app/services/precisao.py.
    ponto_confirmado: bool = False
    #: Lugar escolhido na busca do Google. So um identificador: a precisao
    #: quem decide e o servidor, conferindo no proprio cache que a
    #: coordenada e a mesma que o Google devolveu.
    google_place_id: str | None = Field(default=None, max_length=300)

    weight_kg: Medida = None
    volume_m3: Medida = None
    length_m: Medida = None

    required_crew: Equipe = 1
    service_time_minutes: TempoServico = None

    priority: Priority = Priority.NORMAL
    time_window_start: time | None = None
    time_window_end: time | None = None
    notes: Observacao = None

    @model_validator(mode="after")
    def _coerencia(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Informe latitude e longitude juntas, ou nenhuma das duas.")

        # Janela invertida so seria descoberta na otimizacao, como "sem
        # solucao" — mensagem inutil para quem digitou o horario errado.
        inicio, fim = self.time_window_start, self.time_window_end
        if inicio is not None and fim is not None and inicio >= fim:
            raise ValueError("O fim da janela de horario precisa ser depois do inicio.")
        return self


class DeliveryCreate(_DeliveryBase):
    scheduled_date: date

    @model_validator(mode="after")
    def _endereco_obrigatorio(self):
        # Entrega sem cliente E sem endereco nao tem para onde ir. Barrar
        # aqui evita descobrir isso no meio do planejamento.
        if self.customer_id is None and not self.address:
            raise ValueError(
                "Informe o endereco da entrega ou selecione um cliente cadastrado."
            )
        return self


class DeliveryUpdate(_DeliveryBase):
    scheduled_date: date | None = None
    required_crew: Annotated[int | None, Field(ge=1, le=20)] = None
    priority: Priority | None = None


class DeliveryStatusChange(BaseModel):
    """Mudanca manual de status feita pelo administrador."""

    status: DeliveryStatus
    reason: FailureReason | None = None
    notes: Observacao = None


class DeliveryClienteRead(BaseModel):
    id: int
    name: str
    phone: str | None

    model_config = {"from_attributes": True}


class DeliveryRead(GeocodeRead):
    id: int
    customer_id: int | None
    customer: DeliveryClienteRead | None

    order_number: str | None
    invoice_number: str | None
    recipient_name: str | None
    recipient_phone: str | None
    description: str | None

    weight_kg: Decimal | None
    volume_m3: Decimal | None
    length_m: Decimal | None

    required_crew: int
    service_time_minutes: int | None

    priority: Priority
    scheduled_date: date
    time_window_start: time | None
    time_window_end: time | None

    status: DeliveryStatus
    notes: str | None
    created_at: datetime
    updated_at: datetime


class DeliveryEventRead(BaseModel):
    id: int
    from_status: str | None
    to_status: str
    reason: str | None
    notes: str | None
    latitude: float | None
    longitude: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DeliveryResumo(BaseModel):
    """Contagem por status, usada pelo painel e pelo planejador."""

    total: int
    por_status: dict[str, int]
    sem_coordenada: int
