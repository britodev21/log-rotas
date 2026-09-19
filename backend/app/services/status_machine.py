"""Maquina de estados do dominio.

Este e o UNICO lugar que autoriza uma mudanca de status. Nenhum endpoint,
nenhum repositorio e nenhum outro service altera `status` diretamente.

O motivo e concreto: sistema logistico morre de estado inconsistente. Uma
entrega que volta de ENTREGUE para PENDENTE, uma rota que e iniciada duas
vezes, uma parada concluida antes da chegada — cada um desses e um bug que
so aparece semanas depois, no relatorio que nao fecha, e que ninguem
consegue mais reconstituir.

Espalhar a validacao garante que uma das copias fique para tras na proxima
alteracao. Concentrar aqui torna a regra legivel e testavel de uma vez.
"""

from __future__ import annotations

from app.core.enums import DeliveryStatus as D
from app.core.enums import PlanStatus as P
from app.core.enums import RouteStatus as R
from app.core.enums import StopStatus as S
from app.core.errors import InvalidStateTransitionError

# --------------------------------------------------------------------------- #
# Entregas
# --------------------------------------------------------------------------- #
TRANSICOES_ENTREGA: dict[str, set[str]] = {
    D.PENDENTE: {D.PLANEJADA, D.CANCELADA},
    # Volta para PENDENTE quando o plano que a continha e descartado.
    D.PLANEJADA: {D.EM_ROTA, D.PENDENTE, D.CANCELADA},
    # ENTREGUE direto e permitido: nem sempre o motorista marca chegada
    # antes de entregar, e recusar isso o faria registrar dado falso para
    # conseguir avancar.
    D.EM_ROTA: {D.CHEGOU, D.ENTREGUE, D.NAO_ENTREGUE},
    # Volta para EM_ROTA se ele marcou chegada por engano.
    D.CHEGOU: {D.ENTREGUE, D.NAO_ENTREGUE, D.EM_ROTA},
    # Terminal: entrega concluida nao volta atras. Corrigir um engano aqui e
    # assunto de estorno com registro proprio, nao de mudar o status.
    D.ENTREGUE: set(),
    # Reagendar uma tentativa frustrada devolve a entrega para a fila.
    D.NAO_ENTREGUE: {D.PENDENTE, D.CANCELADA},
    D.CANCELADA: {D.PENDENTE},
}

TRANSICOES_ROTA: dict[str, set[str]] = {
    R.RASCUNHO: {R.PLANEJADA, R.CANCELADA},
    R.PLANEJADA: {R.INICIADA, R.RASCUNHO, R.CANCELADA},
    R.INICIADA: {R.FINALIZADA, R.CANCELADA},
    R.FINALIZADA: set(),
    R.CANCELADA: set(),
}

TRANSICOES_PLANO: dict[str, set[str]] = {
    P.RASCUNHO: {P.CONFIRMADO, P.DESCARTADO},
    # Confirmado nao volta: as rotas ja existem e podem ter comecado.
    # Desfazer e cancelar as rotas, nao reabrir o plano.
    P.CONFIRMADO: set(),
    P.DESCARTADO: set(),
}

TRANSICOES_PARADA: dict[str, set[str]] = {
    S.PENDENTE: {S.CHEGOU, S.CONCLUIDA, S.PULADA},
    S.CHEGOU: {S.CONCLUIDA, S.PENDENTE},
    S.CONCLUIDA: set(),
    S.PULADA: {S.PENDENTE},
}

_ROTULOS = {
    "entrega": "da entrega",
    "rota": "da rota",
    "plano": "do planejamento",
    "parada": "da parada",
}

_MAPAS = {
    "entrega": TRANSICOES_ENTREGA,
    "rota": TRANSICOES_ROTA,
    "plano": TRANSICOES_PLANO,
    "parada": TRANSICOES_PARADA,
}


def pode(tipo: str, de: str, para: str) -> bool:
    """A transicao e permitida?

    Regravar o MESMO status nao e permitido, e isso e deliberado.

    A versao anterior tratava `de == para` como idempotente, o que parecia
    inofensivo e nao era: confirmar um planejamento duas vezes passava pelas
    duas vezes, gravando eventos duplicados no historico das entregas e
    reatribuindo motoristas. Operacao com efeito colateral precisa ser
    recusada na segunda chamada, nao aceita em silencio.

    Quem precisa de comportamento idempotente de verdade — um endpoint que
    possa ser repetido com seguranca — checa o estado antes de chamar, e
    nao pede a transicao.
    """
    return para in _MAPAS[tipo].get(de, set())


def exigir(tipo: str, de: str, para: str) -> None:
    """Autoriza a transicao ou levanta InvalidStateTransitionError.

    A mensagem nomeia os dois estados porque, quando isso estoura em
    producao, a pergunta seguinte e sempre "saindo de onde para onde".
    """
    if pode(tipo, de, para):
        return

    if de == para:
        raise InvalidStateTransitionError(
            f"O status {_ROTULOS[tipo]} ja e {para}.",
            details={"de": de, "para": para, "permitidos": sorted(_MAPAS[tipo].get(de, set()))},
        )

    permitidos = sorted(_MAPAS[tipo].get(de, set()))
    detalhe = ", ".join(permitidos) if permitidos else "nenhum (estado final)"
    raise InvalidStateTransitionError(
        f"Nao e possivel mudar o status {_ROTULOS[tipo]} de {de} para {para}.",
        details={"de": de, "para": para, "permitidos": permitidos, "explicacao": detalhe},
    )


def e_final(tipo: str, status: str) -> bool:
    return not _MAPAS[tipo].get(status, set())
