"""Relatórios do período — somente `ADMIN`.

O que foi prometido, o que aconteceu, e a diferença entre os dois. Os
números e o que cada um significa estão em `app/services/relatorios.py`.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel

from app.api.deps import AdminUser, DbSession
from app.core.errors import ValidationError
from app.services import relatorios

router = APIRouter(prefix="/relatorios", tags=["Relatorios"])

#: Período máximo numa consulta. Acima disso a conta fica cara e ninguém
#: olha o gráfico mesmo — o CSV resolve análise longa.
MAXIMO_DIAS = 366
PADRAO_DIAS = 30


class RelatorioRead(BaseModel):
    de: date
    ate: date
    motorista_id: int | None
    entregas: dict
    rotas: dict
    pontualidade: dict
    tempo_de_parada: dict
    deslocamento: list[dict]
    por_motorista: list[dict]
    por_dia: list[dict]
    #: Paradas concluídas sem hora de chegada: o que falta da amostra.
    paradas_sem_registro: int


def _periodo(de: date | None, ate: date | None) -> relatorios.Periodo:
    ate = ate or date.today()
    de = de or ate - timedelta(days=PADRAO_DIAS - 1)
    if de > ate:
        raise ValidationError("A data inicial e depois da final.")
    if (ate - de).days + 1 > MAXIMO_DIAS:
        raise ValidationError(f"O periodo maximo e de {MAXIMO_DIAS} dias.")
    return relatorios.Periodo(de=de, ate=ate)


@router.get("", response_model=RelatorioRead, summary="Relatorio do periodo")
def relatorio(
    session: DbSession,
    _: AdminUser,
    de: Annotated[date | None, Query()] = None,
    ate: Annotated[date | None, Query()] = None,
    motorista_id: Annotated[int | None, Query()] = None,
) -> RelatorioRead:
    """Entregas, insucessos, pontualidade e a calibração dos tempos.

    Sem datas, os últimos 30 dias. `motorista_id` filtra tudo menos o bloco
    por motorista, que existe justamente para comparar.
    """
    periodo = _periodo(de, ate)
    dados = relatorios.completo(session, periodo, motorista_id)
    dados["paradas_sem_registro"] = relatorios.paradas_sem_registro(
        session, periodo, motorista_id
    )
    return RelatorioRead(**dados)


@router.get("/entregas.csv", summary="Entregas do periodo em CSV")
def entregas_csv(
    session: DbSession,
    _: AdminUser,
    de: Annotated[date | None, Query()] = None,
    ate: Annotated[date | None, Query()] = None,
    motorista_id: Annotated[int | None, Query()] = None,
) -> Response:
    """Uma linha por entrega, com previsto e realizado lado a lado.

    Separado por `;` e com BOM: é assim que o Excel em português abre com as
    colunas certas e os acentos certos, sem ninguém importar nada.
    """
    periodo = _periodo(de, ate)
    conteudo = relatorios.csv_das_entregas(session, periodo, motorista_id)
    nome = f"entregas-{periodo.de.isoformat()}-a-{periodo.ate.isoformat()}.csv"
    return Response(
        content=conteudo,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )
