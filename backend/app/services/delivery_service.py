"""Regras de negocio das entregas."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import DeliveryStatus, FailureReason, GeocodePrecision, GeocodeStatus
from app.core.errors import NotFoundError, ValidationError
from app.models.delivery import Delivery
from app.models.delivery_event import DeliveryEvent
from app.models.user import User
from app.repositories.cadastros_repository import CustomerRepository
from app.repositories.delivery_repository import DeliveryRepository
from app.schemas.delivery import DeliveryCreate, DeliveryStatusChange, DeliveryUpdate
from app.services import status_machine
from app.services.cadastros_service import (
    _aplicar,
    _reavaliar_geocodificacao,
    tirar_origem,
)

logger = logging.getLogger(__name__)

#: Status que significam "a entrega ja esta comprometida com uma rota".
#: Alterar peso, endereco ou data depois disso invalidaria o planejamento
#: em silencio — o veiculo ja foi escolhido contando com aqueles numeros.
EM_EXECUCAO = {
    DeliveryStatus.EM_ROTA.value,
    DeliveryStatus.CHEGOU.value,
    DeliveryStatus.ENTREGUE.value,
}

#: Campos que afetam o planejamento e por isso ficam travados em rota.
CAMPOS_DE_PLANEJAMENTO = {
    "address",
    "latitude",
    "longitude",
    "weight_kg",
    "volume_m3",
    "length_m",
    "required_crew",
    "service_time_minutes",
    "scheduled_date",
    "time_window_start",
    "time_window_end",
    "customer_id",
}


class DeliveryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = DeliveryRepository(session)
        self.clientes = CustomerRepository(session)

    # --- leitura ----------------------------------------------------------- #
    def get(self, delivery_id: int) -> Delivery:
        entrega = self.repo.get(delivery_id)
        if entrega is None:
            raise NotFoundError("Entrega nao encontrada.")
        return entrega

    def listar(self, **filtros) -> list[Delivery]:
        return self.repo.listar(**filtros)

    def resumo(self, data: date | None = None) -> dict:
        return self.repo.resumo(data)

    def historico(self, delivery_id: int) -> list[DeliveryEvent]:
        self.get(delivery_id)  # garante que existe
        return self.repo.eventos(delivery_id)

    # --- escrita ----------------------------------------------------------- #
    def criar(self, payload: DeliveryCreate, *, actor: User | None = None) -> Delivery:
        dados = payload.model_dump()
        self._herdar_do_cliente(dados)
        origem = tirar_origem(self.session, dados)

        entrega = Delivery(**dados, status=DeliveryStatus.PENDENTE.value)
        _reavaliar_geocodificacao(entrega, dados, origem)

        self.repo.add(entrega)
        self._registrar(entrega, None, DeliveryStatus.PENDENTE.value, actor=actor)

        self.session.commit()
        logger.info("Entrega %s criada para %s.", entrega.id, entrega.scheduled_date)
        return entrega

    def atualizar(
        self, delivery_id: int, payload: DeliveryUpdate, *, actor: User | None = None
    ) -> Delivery:
        entrega = self.get(delivery_id)
        dados = payload.model_dump(exclude_unset=True)
        origem = tirar_origem(self.session, dados)

        # Trava explicita, com mensagem que diz o que fazer. Deixar passar
        # mudaria o peso de uma carga que ja esta no caminhao.
        if entrega.status in EM_EXECUCAO:
            travados = CAMPOS_DE_PLANEJAMENTO & dados.keys()
            if travados:
                raise ValidationError(
                    "Esta entrega ja esta em rota; dados que afetam o planejamento "
                    "nao podem mais ser alterados. Cancele a rota para reabri-la.",
                    details={"campos_bloqueados": sorted(travados)},
                )

        if "customer_id" in dados:
            self._herdar_do_cliente(dados, forcar=False)
            origem = origem.ou(tirar_origem(self.session, dados))

        _aplicar(entrega, dados)
        _reavaliar_geocodificacao(entrega, dados, origem)

        self.session.commit()
        return entrega

    def mudar_status(
        self,
        delivery_id: int,
        payload: DeliveryStatusChange,
        *,
        actor: User | None = None,
    ) -> Delivery:
        entrega = self.get(delivery_id)
        anterior = entrega.status
        novo = payload.status.value

        status_machine.exigir("entrega", anterior, novo)

        # Insucesso sem motivo nao vira relatorio. Exigir aqui e o que torna
        # possivel responder depois "por que nao entregamos".
        if novo == DeliveryStatus.NAO_ENTREGUE.value and payload.reason is None:
            raise ValidationError("Informe o motivo da entrega nao realizada.")
        if payload.reason is FailureReason.OUTRO and not payload.notes:
            raise ValidationError('Descreva o motivo quando selecionar "Outro".')

        entrega.status = novo
        self._registrar(
            entrega,
            anterior,
            novo,
            actor=actor,
            reason=payload.reason.value if payload.reason else None,
            notes=payload.notes,
        )

        self.session.commit()
        logger.info("Entrega %s: %s -> %s.", entrega.id, anterior, novo)
        return entrega

    # --- apoio ------------------------------------------------------------- #
    def _herdar_do_cliente(self, dados: dict[str, Any], *, forcar: bool = True) -> None:
        """Copia endereco e coordenada do cliente quando a entrega nao traz.

        Copia, nao referencia: o endereco de entrega pode ser diferente do
        cadastro (obra, outro deposito), e a entrega precisa guardar para
        onde ela foi de fato — mesmo que o cliente mude de endereco depois.
        """
        customer_id = dados.get("customer_id")
        if customer_id is None:
            return

        cliente = self.clientes.get(customer_id)
        if cliente is None:
            raise NotFoundError("O cliente informado nao existe.")

        if not dados.get("address") and cliente.address:
            dados["address"] = cliente.address
            if cliente.latitude is not None and cliente.longitude is not None:
                dados["latitude"] = float(cliente.latitude)
                dados["longitude"] = float(cliente.longitude)
                # A confirmacao viaja junto com a coordenada, e e o que faz
                # "conferir uma vez" valer a pena: quem ja marcou o portao
                # deste cliente nao marca de novo a cada pedido. Sem isto,
                # cliente recorrente voltaria para a fila toda semana.
                if cliente.geocode_status == GeocodeStatus.MANUAL.value:
                    dados["ponto_confirmado"] = True
                elif cliente.geocode_precision == GeocodePrecision.EXATO.value:
                    # O Google provou o ponto do cliente; a entrega herda a
                    # prova junto com a coordenada.
                    dados["_precisao_herdada"] = cliente.geocode_precision
                    dados["_provedor_herdado"] = cliente.geocode_provider

        if forcar and not dados.get("recipient_name"):
            dados["recipient_name"] = cliente.name
        if forcar and not dados.get("recipient_phone"):
            dados["recipient_phone"] = cliente.phone

    def _registrar(
        self,
        entrega: Delivery,
        de: str | None,
        para: str,
        *,
        actor: User | None = None,
        reason: str | None = None,
        notes: str | None = None,
        route_stop_id: int | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> None:
        self.repo.registrar_evento(
            DeliveryEvent(
                delivery_id=entrega.id,
                route_stop_id=route_stop_id,
                from_status=de,
                to_status=para,
                reason=reason,
                notes=notes,
                actor_user_id=actor.id if actor else None,
                latitude=latitude,
                longitude=longitude,
            )
        )


def entregas_sem_coordenada(entregas: list[Delivery]) -> list[Delivery]:
    """Entregas que nao podem entrar num planejamento.

    Usado pelo planejador para recusar o calculo com lista explicita, em vez
    de simplesmente ignorar essas entregas — que sumiriam sem ninguem notar.
    """
    return [
        e
        for e in entregas
        if e.latitude is None
        or e.longitude is None
        or e.geocode_status in {GeocodeStatus.FALHOU.value, GeocodeStatus.PENDENTE.value}
    ]
