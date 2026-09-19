"""Entregas — cadastro, consulta e mudanca manual de status."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, DbSession
from app.core.enums import DeliveryStatus, Priority
from app.schemas.delivery import (
    DeliveryCreate,
    DeliveryEventRead,
    DeliveryRead,
    DeliveryResumo,
    DeliveryStatusChange,
    DeliveryUpdate,
)
from app.services.delivery_service import DeliveryService

router = APIRouter(prefix="/entregas", tags=["Entregas"])


@router.get("", response_model=list[DeliveryRead], summary="Listar entregas")
def listar(
    session: DbSession,
    _: AdminUser,
    data: Annotated[date | None, Query(description="Data exata da entrega.")] = None,
    data_de: Annotated[date | None, Query()] = None,
    data_ate: Annotated[date | None, Query()] = None,
    status_: Annotated[
        list[DeliveryStatus] | None,
        Query(alias="status", description="Um ou mais status."),
    ] = None,
    priority: Annotated[Priority | None, Query()] = None,
    customer_id: Annotated[int | None, Query()] = None,
    sem_coordenada: Annotated[
        bool | None, Query(description="Só entregas que ainda não têm coordenada.")
    ] = None,
    search: Annotated[str | None, Query(max_length=120)] = None,
) -> list[DeliveryRead]:
    entregas = DeliveryService(session).listar(
        data=data,
        data_de=data_de,
        data_ate=data_ate,
        status=[s.value for s in status_] if status_ else None,
        priority=priority.value if priority else None,
        customer_id=customer_id,
        sem_coordenada=sem_coordenada,
        search=search,
    )
    return [DeliveryRead.model_validate(e) for e in entregas]


@router.get("/resumo", response_model=DeliveryResumo, summary="Contagem por status")
def resumo(
    session: DbSession,
    _: AdminUser,
    data: Annotated[date | None, Query()] = None,
) -> DeliveryResumo:
    return DeliveryResumo(**DeliveryService(session).resumo(data))


@router.post(
    "",
    response_model=DeliveryRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar entrega",
)
def criar(payload: DeliveryCreate, session: DbSession, admin: AdminUser) -> DeliveryRead:
    """Endereço ou cliente é obrigatório — entrega sem destino não tem para onde ir.

    Selecionando um cliente, o endereço e a coordenada dele são **copiados**
    para a entrega, não referenciados: o cliente pode mudar de endereço
    depois, e a entrega precisa guardar para onde ela foi de fato.
    """
    return DeliveryRead.model_validate(DeliveryService(session).criar(payload, actor=admin))


@router.get("/{delivery_id}", response_model=DeliveryRead, summary="Detalhe da entrega")
def obter(delivery_id: int, session: DbSession, _: AdminUser) -> DeliveryRead:
    return DeliveryRead.model_validate(DeliveryService(session).get(delivery_id))


@router.get(
    "/{delivery_id}/historico",
    response_model=list[DeliveryEventRead],
    summary="Histórico da entrega",
)
def historico(delivery_id: int, session: DbSession, _: AdminUser) -> list[DeliveryEventRead]:
    """Registro append-only de cada mudança de status.

    É o que permite responder, semanas depois, por que uma entrega não foi
    feita — com horário, motivo e, quando o aparelho permitiu, a coordenada
    de onde o motorista registrou.
    """
    eventos = DeliveryService(session).historico(delivery_id)
    return [DeliveryEventRead.model_validate(e) for e in eventos]


@router.patch("/{delivery_id}", response_model=DeliveryRead, summary="Alterar entrega")
def atualizar(
    delivery_id: int, payload: DeliveryUpdate, session: DbSession, admin: AdminUser
) -> DeliveryRead:
    """Entrega já em rota trava os campos que afetam o planejamento.

    Peso, endereço, data e janela de horário foram usados para escolher o
    veículo e montar a sequência; alterá-los depois invalidaria a rota em
    silêncio. Responde **422** listando os campos bloqueados.
    """
    return DeliveryRead.model_validate(
        DeliveryService(session).atualizar(delivery_id, payload, actor=admin)
    )


@router.post("/{delivery_id}/status", response_model=DeliveryRead, summary="Mudar status")
def mudar_status(
    delivery_id: int,
    payload: DeliveryStatusChange,
    session: DbSession,
    admin: AdminUser,
) -> DeliveryRead:
    """Transição validada pela máquina de estados.

    Responde **409** com os status permitidos quando a mudança é impossível.
    `NAO_ENTREGUE` exige motivo, e o motivo `OUTRO` exige descrição — sem
    isso o relatório de insucesso não diria nada.
    """
    return DeliveryRead.model_validate(
        DeliveryService(session).mudar_status(delivery_id, payload, actor=admin)
    )
