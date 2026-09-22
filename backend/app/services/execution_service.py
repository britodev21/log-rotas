"""Execucao da rota pelo motorista.

Toda operacao aqui passa por duas verificacoes antes de qualquer outra
coisa:

1. a rota/parada pertence a ESTE motorista;
2. a transicao de status e permitida.

A primeira e seguranca: o motorista nao pode marcar entrega de colega, nem
por engano nem de proposito. A segunda e integridade: entrega so e concluida
depois de a rota comecar.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import DeliveryStatus, FailureReason, RouteStatus, StopStatus, StopType
from app.core.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.models.driver import Driver
from app.models.route import Route, RouteStop, RouteStopDelivery
from app.models.user import User
from app.services import status_machine
from app.services.delivery_service import DeliveryService

logger = logging.getLogger(__name__)

#: Status de rota que o motorista pode ver na tela dele. RASCUNHO fica de
#: fora de proposito: e planejamento nao confirmado, e mostra-lo faria o
#: motorista sair para uma rota que o administrador ainda esta revisando.
VISIVEIS_AO_MOTORISTA = [
    RouteStatus.PLANEJADA.value,
    RouteStatus.INICIADA.value,
    RouteStatus.FINALIZADA.value,
]


class ExecutionService:
    def __init__(self, session: Session, usuario: User) -> None:
        self.session = session
        self.usuario = usuario
        self.entregas = DeliveryService(session)

    # ------------------------------------------------------------------ #
    # Quem e este motorista
    # ------------------------------------------------------------------ #
    def perfil(self) -> Driver:
        motorista = self.session.scalars(
            select(Driver).where(Driver.user_id == self.usuario.id)
        ).first()

        if motorista is None:
            raise NotFoundError(
                "Seu acesso ainda nao esta vinculado a um cadastro de motorista. "
                "Peca ao administrador para fazer o vinculo."
            )
        if not motorista.active:
            raise PermissionDeniedError("Seu cadastro de motorista esta inativo.")
        return motorista

    # ------------------------------------------------------------------ #
    # Leitura
    # ------------------------------------------------------------------ #
    def rotas_do_dia(self, dia: date | None = None) -> list[Route]:
        motorista = self.perfil()
        alvo = dia or date.today()

        stmt = (
            select(Route)
            .where(
                Route.driver_id == motorista.id,
                Route.date == alvo,
                Route.status.in_(VISIVEIS_AO_MOTORISTA),
            )
            .order_by(Route.sequence_in_day, Route.id)
        )
        return list(self.session.scalars(stmt).unique())

    def rota(self, rota_id: int) -> Route:
        """Carrega a rota conferindo que ela e deste motorista.

        A conferencia acontece aqui, no unico caminho de leitura, e nao em
        cada endpoint. Endpoint novo que esqueca de verificar nao existe
        porque nao ha outro jeito de obter a rota.
        """
        motorista = self.perfil()
        rota = self.session.get(Route, rota_id)

        if rota is None or rota.driver_id != motorista.id:
            # 404, nao 403: responder "existe mas nao e sua" confirmaria a
            # existencia de rotas alheias a quem esta sondando.
            raise NotFoundError("Rota nao encontrada.")

        if rota.status not in VISIVEIS_AO_MOTORISTA:
            raise NotFoundError("Rota nao encontrada.")

        return rota

    def parada(self, parada_id: int) -> RouteStop:
        parada = self.session.get(RouteStop, parada_id)
        if parada is None:
            raise NotFoundError("Parada nao encontrada.")
        self.rota(parada.route_id)  # valida a posse
        return parada

    def item(self, item_id: int) -> RouteStopDelivery:
        item = self.session.get(RouteStopDelivery, item_id)
        if item is None:
            raise NotFoundError("Entrega nao encontrada.")
        self.parada(item.route_stop_id)  # valida a posse
        return item

    # ------------------------------------------------------------------ #
    # Execucao
    # ------------------------------------------------------------------ #
    def iniciar_rota(self, rota_id: int) -> Route:
        rota = self.rota(rota_id)
        status_machine.exigir("rota", rota.status, RouteStatus.INICIADA.value)

        # O banco tambem impede, por indice parcial. Esta checagem existe
        # para a mensagem ser util em vez de um erro de constraint.
        em_andamento = self.session.scalars(
            select(Route).where(
                Route.driver_id == rota.driver_id,
                Route.status == RouteStatus.INICIADA.value,
            )
        ).first()
        if em_andamento is not None:
            raise ConflictError(
                f"Voce ja tem a rota #{em_andamento.id} em andamento. "
                "Finalize-a antes de comecar outra."
            )

        rota.status = RouteStatus.INICIADA.value
        rota.started_at = datetime.now(UTC)

        # As entregas da PRIMEIRA viagem entram em rota junto: o motorista
        # saiu com essa carga. As das viagens seguintes ficam PLANEJADA —
        # ainda estao na base, e o painel nao pode mostra-las como se
        # estivessem no caminhao. Elas saem na recarga.
        self._carregar(rota, viagem=1)

        self.session.commit()
        logger.info("Rota %s iniciada pelo motorista %s.", rota.id, rota.driver_id)
        return rota

    def concluir_recarga(self, parada_id: int) -> RouteStop:
        """O caminhao foi recarregado na base e sai para a proxima viagem.

        Recusa se alguma entrega da viagem anterior ficou sem registro: o
        motorista esta na base com o caminhao, e a entrega que voltou precisa
        ser dita "nao entregue", com o motivo — nao sumir.
        """
        parada = self.parada(parada_id)
        rota = self.rota(parada.route_id)
        if rota.status != RouteStatus.INICIADA.value:
            raise ValidationError("Inicie a rota antes de registrar a recarga.")
        if parada.stop_type != StopType.BASE_RECARGA.value:
            raise ValidationError("Esta parada nao e uma recarga na base.")
        if parada.status != StopStatus.CHEGOU.value:
            raise ValidationError(
                "Registre a chegada na base antes de concluir a recarga."
                if parada.status == StopStatus.PENDENTE.value
                else "Esta recarga ja foi concluida."
            )

        sem_registro = [
            item
            for s in rota.stops
            if s.stop_type == StopType.ENTREGA.value and s.trip_number < parada.trip_number
            for item in s.items
            if item.status not in _RESOLVIDOS
        ]
        if sem_registro:
            raise ValidationError(
                f"{len(sem_registro)} entrega(s) da viagem anterior ainda sem registro. "
                "Marque cada uma como entregue ou nao entregue antes de sair de novo.",
                details={"itens": [i.id for i in sem_registro]},
            )

        parada.status = StopStatus.CONCLUIDA.value
        parada.departed_at = datetime.now(UTC)
        self._carregar(rota, viagem=parada.trip_number)

        self.session.commit()
        logger.info(
            "Rota %s: recarga concluida, viagem %s em andamento.", rota.id, parada.trip_number
        )
        return parada

    def _carregar(self, rota: Route, *, viagem: int) -> None:
        """As entregas da viagem saem da base: PLANEJADA -> EM_ROTA."""
        for parada in rota.stops:
            if parada.trip_number != viagem:
                continue
            for item in parada.items:
                entrega = item.delivery
                if status_machine.pode("entrega", entrega.status, DeliveryStatus.EM_ROTA.value):
                    anterior = entrega.status
                    entrega.status = DeliveryStatus.EM_ROTA.value
                    item.status = DeliveryStatus.EM_ROTA.value
                    self.entregas._registrar(
                        entrega,
                        anterior,
                        DeliveryStatus.EM_ROTA.value,
                        actor=self.usuario,
                        route_stop_id=parada.id,
                    )

    @staticmethod
    def viagem_atual(rota: Route) -> int:
        """A viagem em andamento: a primeira, mais uma por recarga concluida."""
        return 1 + sum(
            1
            for s in rota.stops
            if s.stop_type == StopType.BASE_RECARGA.value
            and s.status == StopStatus.CONCLUIDA.value
        )

    def _exigir_viagem_liberada(self, rota: Route, parada: RouteStop) -> None:
        """Parada de uma viagem que ainda nao saiu da base nao se resolve.

        A recarga de uma viagem pode receber a chegada (o motorista chegou a
        base); as entregas dela, nao — a carga ainda nao esta no caminhao.
        """
        atual = self.viagem_atual(rota)
        e_recarga = parada.stop_type == StopType.BASE_RECARGA.value
        limite = atual + 1 if e_recarga else atual
        if parada.trip_number > limite:
            raise ValidationError(
                f"Esta parada e da viagem {parada.trip_number}. Volte a base e conclua "
                "a recarga antes."
            )

    def registrar_chegada(
        self, parada_id: int, *, latitude: float | None = None, longitude: float | None = None
    ) -> RouteStop:
        parada = self.parada(parada_id)
        rota = self.rota(parada.route_id)

        if rota.status != RouteStatus.INICIADA.value:
            raise ValidationError("Inicie a rota antes de registrar chegada.")
        self._exigir_viagem_liberada(rota, parada)

        status_machine.exigir("parada", parada.status, StopStatus.CHEGOU.value)
        parada.status = StopStatus.CHEGOU.value
        parada.arrived_at = datetime.now(UTC)

        for item in parada.items:
            entrega = item.delivery
            if status_machine.pode("entrega", entrega.status, DeliveryStatus.CHEGOU.value):
                anterior = entrega.status
                entrega.status = DeliveryStatus.CHEGOU.value
                item.status = DeliveryStatus.CHEGOU.value
                self.entregas._registrar(
                    entrega,
                    anterior,
                    DeliveryStatus.CHEGOU.value,
                    actor=self.usuario,
                    route_stop_id=parada.id,
                    latitude=latitude,
                    longitude=longitude,
                )

        self.session.commit()
        return parada

    def concluir_entrega(
        self,
        item_id: int,
        *,
        recebedor: str | None = None,
        observacao: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> RouteStopDelivery:
        item = self.item(item_id)
        self._exigir_rota_iniciada(item)

        entrega = item.delivery
        status_machine.exigir("entrega", entrega.status, DeliveryStatus.ENTREGUE.value)

        anterior = entrega.status
        entrega.status = DeliveryStatus.ENTREGUE.value
        item.status = DeliveryStatus.ENTREGUE.value
        item.delivered_at = datetime.now(UTC)
        item.receiver_name = recebedor
        item.notes = observacao

        self.entregas._registrar(
            entrega,
            anterior,
            DeliveryStatus.ENTREGUE.value,
            actor=self.usuario,
            notes=observacao,
            route_stop_id=item.route_stop_id,
            latitude=latitude,
            longitude=longitude,
        )

        self._fechar_parada_se_concluida(item.route_stop_id)
        self.session.commit()
        return item

    def registrar_insucesso(
        self,
        item_id: int,
        *,
        motivo: FailureReason,
        observacao: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> RouteStopDelivery:
        item = self.item(item_id)
        self._exigir_rota_iniciada(item)

        # Motivo OUTRO sem descricao produziria relatorio que nao explica
        # nada — e o relatorio de insucesso e justamente o que a empresa vai
        # usar contra reclamacao de cliente.
        if motivo is FailureReason.OUTRO and not observacao:
            raise ValidationError('Descreva o que aconteceu quando escolher "Outro".')

        entrega = item.delivery
        status_machine.exigir("entrega", entrega.status, DeliveryStatus.NAO_ENTREGUE.value)

        anterior = entrega.status
        entrega.status = DeliveryStatus.NAO_ENTREGUE.value
        item.status = DeliveryStatus.NAO_ENTREGUE.value
        item.failure_reason = motivo.value
        item.notes = observacao

        self.entregas._registrar(
            entrega,
            anterior,
            DeliveryStatus.NAO_ENTREGUE.value,
            actor=self.usuario,
            reason=motivo.value,
            notes=observacao,
            route_stop_id=item.route_stop_id,
            latitude=latitude,
            longitude=longitude,
        )

        self._fechar_parada_se_concluida(item.route_stop_id)
        self.session.commit()
        return item

    def finalizar_rota(self, rota_id: int) -> Route:
        rota = self.rota(rota_id)
        status_machine.exigir("rota", rota.status, RouteStatus.FINALIZADA.value)

        # Entrega que ficou sem resposta nao pode virar "entregue" por
        # omissao: ela volta a ser pendente e reaparece no planejamento de
        # outro dia. O contrario esconderia servico nao feito.
        pendentes = 0
        for parada in rota.stops:
            for item in parada.items:
                entrega = item.delivery
                if entrega.status in (
                    DeliveryStatus.EM_ROTA.value,
                    DeliveryStatus.CHEGOU.value,
                    DeliveryStatus.PLANEJADA.value,
                ):
                    anterior = entrega.status
                    entrega.status = DeliveryStatus.NAO_ENTREGUE.value
                    item.status = DeliveryStatus.NAO_ENTREGUE.value
                    item.failure_reason = FailureReason.OUTRO.value
                    item.notes = "Rota finalizada sem registro desta entrega."
                    self.entregas._registrar(
                        entrega,
                        anterior,
                        DeliveryStatus.NAO_ENTREGUE.value,
                        actor=self.usuario,
                        reason=FailureReason.OUTRO.value,
                        notes="Rota finalizada sem registro desta entrega.",
                        route_stop_id=parada.id,
                    )
                    pendentes += 1

            if parada.status != StopStatus.CONCLUIDA.value:
                parada.status = StopStatus.CONCLUIDA.value

        rota.status = RouteStatus.FINALIZADA.value
        rota.finished_at = datetime.now(UTC)

        self.session.commit()
        logger.info(
            "Rota %s finalizada; %s entrega(s) sem registro foram marcadas como nao entregues.",
            rota.id,
            pendentes,
        )
        return rota

    # ------------------------------------------------------------------ #
    def _exigir_rota_iniciada(self, item: RouteStopDelivery) -> None:
        parada = self.session.get(RouteStop, item.route_stop_id)
        rota = self.session.get(Route, parada.route_id)
        if rota.status != RouteStatus.INICIADA.value:
            raise ValidationError(
                "Inicie a rota antes de registrar entregas."
                if rota.status == RouteStatus.PLANEJADA.value
                else "Esta rota nao esta mais em andamento."
            )
        self._exigir_viagem_liberada(rota, parada)

    def _fechar_parada_se_concluida(self, parada_id: int) -> None:
        """Fecha a parada quando todas as entregas dela foram resolvidas."""
        parada = self.session.get(RouteStop, parada_id)
        if all(i.status in _RESOLVIDOS for i in parada.items):
            parada.status = StopStatus.CONCLUIDA.value
            parada.departed_at = datetime.now(UTC)


_RESOLVIDOS = frozenset(
    {
        DeliveryStatus.ENTREGUE.value,
        DeliveryStatus.NAO_ENTREGUE.value,
        DeliveryStatus.CANCELADA.value,
    }
)


def progresso(rota: Route) -> dict:
    """Quantas entregas ja foram resolvidas nesta rota."""
    total = 0
    concluidas = 0
    for parada in rota.stops:
        for item in parada.items:
            total += 1
            if item.status in (
                DeliveryStatus.ENTREGUE.value,
                DeliveryStatus.NAO_ENTREGUE.value,
                DeliveryStatus.CANCELADA.value,
            ):
                concluidas += 1

    return {
        "total": total,
        "concluidas": concluidas,
        "restantes": total - concluidas,
        "percentual": round(concluidas / total * 100) if total else 0,
    }
