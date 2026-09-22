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
from app.core.enums import RouteStatus
from app.core.errors import ValidationError
from app.schemas.driver import (
    ChegadaRequest,
    EntregaRealizadaRequest,
    InsucessoRequest,
    RotaMotoristaRead,
)
from app.schemas.planning import ParadaRead
from app.schemas.rastreamento import (
    EnvioPosicoes,
    ManobraRead,
    NavegacaoRead,
    ParadaNavegacaoRead,
    ResultadoEnvioRead,
)
from app.services.execution_service import ExecutionService, progresso
from app.services.rastreamento import PosicaoRecebida, RastreamentoService

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


# --------------------------------------------------------------------------- #
# Rastreamento e navegacao
# --------------------------------------------------------------------------- #
@router.post(
    "/rotas/{rota_id}/posicoes",
    response_model=ResultadoEnvioRead,
    summary="Enviar posicoes do GPS",
)
def enviar_posicoes(
    rota_id: int, payload: EnvioPosicoes, session: DbSession, usuario: DriverUser
) -> ResultadoEnvioRead:
    """Recebe o GPS do celular em lote.

    Lote porque o celular guarda o que nao conseguiu mandar num trecho sem
    sinal. Ponto ruim (GPS impreciso, relogio adiantado) e descartado e
    CONTADO, com o motivo — nunca derruba o lote inteiro.

    Com a rota fora de execucao, tudo e descartado: a posicao do motorista
    so e assunto do sistema durante a rota.
    """
    rota = ExecutionService(session, usuario).rota(rota_id)
    resultado = RastreamentoService(session).registrar(
        rota,
        [
            PosicaoRecebida(
                latitude=p.latitude,
                longitude=p.longitude,
                registrada_em=p.registrada_em,
                precisao_m=p.precisao_m,
                velocidade_mps=p.velocidade_mps,
                direcao_graus=p.direcao_graus,
            )
            for p in payload.posicoes
        ],
    )
    return ResultadoEnvioRead(
        aceitas=resultado.aceitas,
        repetidas=resultado.repetidas,
        descartadas=resultado.descartadas,
        motivos=resultado.motivos,
    )


@router.get(
    "/rotas/{rota_id}/navegacao",
    response_model=NavegacaoRead,
    summary="Rota ate a proxima parada",
)
def navegacao(
    rota_id: int,
    session: DbSession,
    usuario: DriverUser,
    latitude: Annotated[float, Query(ge=-90, le=90)],
    longitude: Annotated[float, Query(ge=-180, le=180)],
) -> NavegacaoRead:
    """Da posicao atual ate a proxima parada, com as manobras em portugues.

    O destino e o ponto na rua do endereco mais proximo do pino, e nao o
    pino: o pino fica no lote, e a rua mais proxima dele pode ser a de tras.
    """
    rota = ExecutionService(session, usuario).rota(rota_id)
    if rota.status != RouteStatus.INICIADA.value:
        raise ValidationError("Inicie a rota para navegar.")

    dados = RastreamentoService(session).navegar(rota, (latitude, longitude))
    if dados["concluida"]:
        return NavegacaoRead(concluida=True)

    parada = dados["parada"]
    trajeto = dados["trajeto"]
    manobras = trajeto.pernas[0].manobras if trajeto.pernas else []
    return NavegacaoRead(
        concluida=False,
        parada=ParadaNavegacaoRead(
            id=parada.id,
            tipo=parada.stop_type,
            sequencia=parada.sequence,
            rotulo=parada.label,
            endereco=parada.address,
            latitude=float(parada.latitude),
            longitude=float(parada.longitude),
            status=parada.status,
            entregas=len(parada.items),
        ),
        latitude_chegada=dados["ponto_chegada"][0],
        longitude_chegada=dados["ponto_chegada"][1],
        geometria=trajeto.geometria,
        manobras=[ManobraRead(**vars(m)) for m in manobras],
        distancia_m=trajeto.distancia_m,
        duracao_s=dados["duracao_s"],
        chegada_prevista=dados["chegada_prevista"],
        com_transito=dados["com_transito"],
        estimada=trajeto.estimada,
        aviso=trajeto.aviso,
    )
