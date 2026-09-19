"""Geocodificação e fila de revisão de endereços."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import or_, select

from app.api.deps import AdminUser, DbSession
from app.core.enums import GeocodeStatus
from app.geocoding.service import ALVOS, GeocodingService
from app.models.base_location import BaseLocation
from app.models.customer import Customer
from app.models.delivery import Delivery
from app.schemas.geocoding import (
    CoordenadaManual,
    GeocodeTentativaRead,
    LoteRequest,
    LoteResultado,
    PendenteRead,
)
from app.services.delivery_service import DeliveryService

router = APIRouter(prefix="/geocodificacao", tags=["Geocodificacao"])

#: Situações que exigem intervenção humana. `PENDENTE` entra porque, sem
#: coordenada, a entrega não pode ser planejada — e o administrador precisa
#: saber disso antes de tentar montar a rota, não durante.
PRECISAM_ATENCAO = [
    GeocodeStatus.PENDENTE.value,
    GeocodeStatus.AMBIGUO.value,
    GeocodeStatus.FALHOU.value,
]


@router.get(
    "/pendentes",
    response_model=list[PendenteRead],
    summary="Endereços que precisam de atenção",
)
def pendentes(
    session: DbSession,
    _: AdminUser,
    tipo: Annotated[str | None, Query(description="entrega, cliente ou base.")] = None,
    limite: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[PendenteRead]:
    """Fila de revisão de endereços.

    Reúne o que não virou coordenada confiável: sem endereço resolvido, a
    entrega não entra no planejamento. Esta tela existe para o problema
    aparecer antes de o administrador tentar calcular as rotas.
    """
    resultado: list[PendenteRead] = []

    consultas = {
        "entrega": (Delivery, lambda d: d.recipient_name or d.description or f"Entrega {d.id}"),
        "cliente": (Customer, lambda c: c.name),
        "base": (BaseLocation, lambda b: b.name),
    }

    for nome, (modelo, titulo) in consultas.items():
        if tipo and tipo != nome:
            continue

        stmt = (
            select(modelo)
            .where(
                modelo.geocode_status.in_(PRECISAM_ATENCAO),
                # Registro sem endereço nenhum não é problema de
                # geocodificação — é cadastro incompleto, e aparecer aqui
                # só poluiria a fila.
                or_(
                    modelo.address.is_not(None),
                    modelo.geocode_status != GeocodeStatus.PENDENTE.value,
                ),
            )
            .limit(limite)
        )

        for registro in session.scalars(stmt).unique():
            resultado.append(
                PendenteRead(
                    tipo=nome,
                    id=registro.id,
                    titulo=titulo(registro),
                    address=registro.address,
                    geocode_status=registro.geocode_status,
                    geocode_error=registro.geocode_error,
                    latitude=float(registro.latitude) if registro.latitude else None,
                    longitude=float(registro.longitude) if registro.longitude else None,
                )
            )

    return resultado


@router.post("/testar", response_model=GeocodeTentativaRead, summary="Testar um endereço")
def testar(
    endereco: Annotated[str, Query(min_length=3, max_length=255)],
    session: DbSession,
    _: AdminUser,
) -> GeocodeTentativaRead:
    """Consulta o provedor sem gravar em nenhum registro.

    Serve para conferir como o endereço será interpretado antes de cadastrar.
    """
    resultado = GeocodingService(session).geocodificar(endereco)
    session.commit()  # o cache foi alimentado
    return GeocodeTentativaRead(**resultado.__dict__)


@router.post(
    "/{tipo}/{registro_id}",
    response_model=GeocodeTentativaRead,
    summary="Geocodificar um registro",
)
def geocodificar_um(
    tipo: str,
    registro_id: int,
    session: DbSession,
    _: AdminUser,
    forcar: Annotated[bool, Query(description="Sobrescreve pino manual.")] = False,
) -> GeocodeTentativaRead:
    """Pino ajustado à mão (`MANUAL`) não é sobrescrito sem `forcar=true`."""
    _, resultado = GeocodingService(session).geocodificar_um(tipo, registro_id, forcar=forcar)
    return GeocodeTentativaRead(**resultado.__dict__)


@router.put(
    "/{tipo}/{registro_id}/coordenada",
    response_model=GeocodeTentativaRead,
    summary="Definir a coordenada manualmente",
)
def definir_coordenada(
    tipo: str, registro_id: int, payload: CoordenadaManual, session: DbSession, _: AdminUser
) -> GeocodeTentativaRead:
    """Grava o pino arrastado no mapa.

    O registro passa a `MANUAL` e a geocodificação automática não o
    sobrescreve mais. É o que permite corrigir um endereço **uma vez** — o
    que importa em Campo Grande, onde loteamento novo e chácara têm
    cobertura irregular no OpenStreetMap.
    """
    registro = GeocodingService(session).definir_coordenada(
        tipo, registro_id, payload.latitude, payload.longitude
    )
    return GeocodeTentativaRead(
        status=registro.geocode_status,
        latitude=float(registro.latitude),
        longitude=float(registro.longitude),
        provider="manual",
    )


@router.post("/lote", response_model=LoteResultado, summary="Geocodificar em lote")
def lote(payload: LoteRequest, session: DbSession, _: AdminUser) -> LoteResultado:
    """Processa uma fila de endereços pendentes.

    **Demora.** O Nominatim permite uma requisição por segundo, então 50
    endereços levam cerca de um minuto — endereços já vistos saem do cache e
    não contam. Um endereço que falha não interrompe os demais.
    """
    modelo = ALVOS[payload.tipo]

    if payload.tipo == "entrega":
        registros = DeliveryService(session).repo.para_geocodificar(payload.limite)
    else:
        estados = PRECISAM_ATENCAO if not payload.forcar else [*PRECISAM_ATENCAO, "OK"]
        stmt = (
            select(modelo)
            .where(modelo.address.is_not(None), modelo.geocode_status.in_(estados))
            .limit(payload.limite)
        )
        registros = list(session.scalars(stmt).unique())

    contagem = GeocodingService(session).geocodificar_lote(registros, forcar=payload.forcar)
    return LoteResultado(processados=len(registros), **contagem)
