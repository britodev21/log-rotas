"""Operação do motorista — a rota do dia, executada pelo celular.

Todas as rotas exigem perfil `MOTORISTA` e só alcançam o que pertence a ele.
A verificação de posse acontece no serviço, num único caminho de leitura:
endpoint novo que esqueça de conferir não existe, porque não há outro jeito
de obter a rota.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import DbSession, DriverUser
from app.schemas.driver import (
    ChegadaRequest,
    EntregaRealizadaRequest,
    InsucessoRequest,
    RotaMotoristaRead,
)
from app.schemas.planning import ParadaRead
from app.services.execution_service import ExecutionService, progresso

router = APIRouter(prefix="/motorista", tags=["Motorista"])


def _montar(rota, servico) -> RotaMotoristaRead:
    leitura = RotaMotoristaRead.model_validate(rota)
    leitura.progresso = progresso(rota)
    return leitura


@router.get("/rotas", response_model=list[RotaMotoristaRead], summary="Minhas rotas do dia")
def minhas_rotas(
    session: DbSession,
    usuario: DriverUser,
    data: Annotated[date | None, Query(description="Padrão: hoje.")] = None,
) -> list[RotaMotoristaRead]:
    """Rotas confirmadas deste motorista.

    Planejamento em rascunho **não** aparece: mostrá-lo faria o motorista
    sair para uma rota que o administrador ainda está revisando.

    Pode haver mais de uma no mesmo dia (turnos), mas só uma fica em
    andamento por vez.
    """
    servico = ExecutionService(session, usuario)
    return [_montar(r, servico) for r in servico.rotas_do_dia(data)]


@router.get("/rotas/{rota_id}", response_model=RotaMotoristaRead, summary="Detalhe da rota")
def detalhe(rota_id: int, session: DbSession, usuario: DriverUser) -> RotaMotoristaRead:
    """Rota de outro motorista responde **404**, não 403.

    Dizer "existe, mas não é sua" confirmaria a existência de rotas alheias
    a quem estivesse sondando.
    """
    servico = ExecutionService(session, usuario)
    return _montar(servico.rota(rota_id), servico)


@router.post(
    "/rotas/{rota_id}/iniciar", response_model=RotaMotoristaRead, summary="Iniciar rota"
)
def iniciar(rota_id: int, session: DbSession, usuario: DriverUser) -> RotaMotoristaRead:
    """Marca a saída da base e coloca as entregas em rota.

    Responde **409** se o motorista já tem outra rota em andamento — o banco
    também impede, por índice parcial; a checagem existe para a mensagem ser
    útil em vez de um erro de constraint.
    """
    servico = ExecutionService(session, usuario)
    return _montar(servico.iniciar_rota(rota_id), servico)


@router.post("/paradas/{parada_id}/cheguei", response_model=ParadaRead, summary="Cheguei")
def cheguei(
    parada_id: int, payload: ChegadaRequest, session: DbSession, usuario: DriverUser
) -> ParadaRead:
    """Registra a chegada na parada, com hora e — quando o aparelho permite —
    a coordenada.

    A coordenada é opcional de propósito: o navegador só libera
    geolocalização em contexto seguro (HTTPS), e nem sempre há sinal.
    Exigir travaria o motorista na calçada.
    """
    parada = ExecutionService(session, usuario).registrar_chegada(
        parada_id, latitude=payload.latitude, longitude=payload.longitude
    )
    return ParadaRead.model_validate(parada)


@router.post(
    "/entregas/{item_id}/entregue",
    response_model=ParadaRead,
    summary="Entrega realizada",
)
def entregue(
    item_id: int, payload: EntregaRealizadaRequest, session: DbSession, usuario: DriverUser
) -> ParadaRead:
    """Conclui **uma** entrega da parada.

    A parada pode ter várias; cada uma é resolvida separadamente, porque o
    cliente A pode receber e o B estar ausente. A parada fecha sozinha
    quando todas forem resolvidas.
    """
    servico = ExecutionService(session, usuario)
    item = servico.concluir_entrega(
        item_id,
        recebedor=payload.recebedor,
        observacao=payload.observacao,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    return ParadaRead.model_validate(servico.parada(item.route_stop_id))


@router.post(
    "/entregas/{item_id}/nao-entregue",
    response_model=ParadaRead,
    summary="Entrega não realizada",
)
def nao_entregue(
    item_id: int, payload: InsucessoRequest, session: DbSession, usuario: DriverUser
) -> ParadaRead:
    """Registra o insucesso com motivo obrigatório.

    O motivo `OUTRO` exige descrição: sem ela o relatório de insucesso não
    explicaria nada — e é justamente esse relatório que a empresa usa contra
    reclamação de cliente.
    """
    servico = ExecutionService(session, usuario)
    item = servico.registrar_insucesso(
        item_id,
        motivo=payload.motivo,
        observacao=payload.observacao,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    return ParadaRead.model_validate(servico.parada(item.route_stop_id))


@router.post(
    "/rotas/{rota_id}/finalizar",
    response_model=RotaMotoristaRead,
    summary="Finalizar rota",
)
def finalizar(rota_id: int, session: DbSession, usuario: DriverUser) -> RotaMotoristaRead:
    """Encerra o dia.

    Entrega que ficou sem resposta **não** vira "entregue" por omissão: ela
    é marcada como não entregue, com a observação de que a rota foi
    finalizada sem registro, e volta a aparecer no planejamento. O contrário
    esconderia serviço não feito.
    """
    servico = ExecutionService(session, usuario)
    return _montar(servico.finalizar_rota(rota_id), servico)
