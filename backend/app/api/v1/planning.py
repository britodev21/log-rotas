"""Planejador de rotas: calcular, revisar, confirmar."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, DbSession
from app.core.enums import MatrixSource, PlanStatus
from app.models.route import RoutePlan
from app.schemas.planning import (
    CalcularRequest,
    ConfirmarRequest,
    PlanoRead,
    PlanoResumo,
)
from app.services.planning_service import PlanningService

router = APIRouter(prefix="/planejamento", tags=["Planejamento"])


def _montar(plano: RoutePlan) -> PlanoRead:
    """Acrescenta ao plano o que a interface precisa saber sobre a qualidade
    do dado — informação que não está numa coluna, mas muda como o resultado
    deve ser lido."""
    leitura = PlanoRead.model_validate(plano)
    leitura.distancias_estimadas = plano.matrix_source == MatrixSource.HAVERSINE.value
    leitura.avisos = (plano.params or {}).get("avisos", [])
    return leitura


@router.post(
    "/calcular",
    response_model=PlanoRead,
    status_code=status.HTTP_201_CREATED,
    summary="Calcular rotas",
)
def calcular(payload: CalcularRequest, session: DbSession, admin: AdminUser) -> PlanoRead:
    """Monta um planejamento e devolve como **rascunho**.

    Nada na operação muda: as entregas continuam `PENDENTE`, nenhuma rota
    fica disponível para motorista. Só `POST /confirmar` transforma isso em
    operação de verdade.

    O que acontece por dentro, em ordem: as entregas são agrupadas por lugar
    (uma parada pode resolver várias), a matriz de distâncias é montada, e o
    OR-Tools resolve minimizando **tempo** — não quilometragem, porque numa
    operação dentro de Campo Grande é o tempo parado que limita o dia.

    Respostas de recusa, todas com o motivo:

    - **422** entregas sem coordenada, com a lista — ignorá-las faria
      entregas sumirem do plano sem ninguém perceber;
    - **422** base sem coordenada, veículo ou motorista inativo;
    - **409** entregas que não estão mais pendentes;
    - **409** o solver não encontrou solução, com as estatísticas.

    Nunca devolve uma ordenação qualquer apresentada como otimização.
    """
    plano = PlanningService(session).calcular(payload, actor=admin)
    return _montar(plano)


@router.get("", response_model=list[PlanoResumo], summary="Listar planejamentos")
def listar(
    session: DbSession,
    _: AdminUser,
    data: Annotated[date | None, Query()] = None,
    status_: Annotated[PlanStatus | None, Query(alias="status")] = None,
) -> list[PlanoResumo]:
    planos = PlanningService(session).listar(
        data=data, status=status_.value if status_ else None
    )
    return [PlanoResumo.model_validate(p) for p in planos]


@router.get("/{plano_id}", response_model=PlanoRead, summary="Detalhe do planejamento")
def obter(plano_id: int, session: DbSession, _: AdminUser) -> PlanoRead:
    return _montar(PlanningService(session).get(plano_id))


@router.post(
    "/{plano_id}/confirmar", response_model=PlanoRead, summary="Confirmar planejamento"
)
def confirmar(
    plano_id: int, payload: ConfirmarRequest, session: DbSession, admin: AdminUser
) -> PlanoRead:
    """Transforma o rascunho em operação.

    As rotas passam a `PLANEJADA`, as entregas a `PLANEJADA`, e cada
    motorista passa a ver a sua rota. **Toda rota precisa de motorista** —
    confirmar com rota órfã responde 422, porque uma rota que ninguém vai
    executar é pior do que nenhuma rota.

    Um plano confirmado não volta atrás: desfazer é cancelar as rotas, que
    podem já ter começado.
    """
    return _montar(PlanningService(session).confirmar(plano_id, payload, actor=admin))


@router.post(
    "/{plano_id}/descartar", response_model=PlanoRead, summary="Descartar planejamento"
)
def descartar(plano_id: int, session: DbSession, _: AdminUser) -> PlanoRead:
    """Joga fora um rascunho.

    As entregas não precisam voltar de status porque nunca saíram de
    `PENDENTE` — é exatamente a vantagem de o cálculo não mexer na operação.
    """
    return _montar(PlanningService(session).descartar(plano_id))
