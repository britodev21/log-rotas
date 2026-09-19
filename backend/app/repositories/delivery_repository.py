"""Acesso a dados de entregas."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import DeliveryStatus, GeocodeStatus
from app.models.delivery import Delivery
from app.models.delivery_event import DeliveryEvent


class DeliveryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, delivery_id: int) -> Delivery | None:
        return self.session.get(Delivery, delivery_id)

    def por_ids(self, ids: list[int]) -> list[Delivery]:
        if not ids:
            return []
        stmt = select(Delivery).where(Delivery.id.in_(ids))
        return list(self.session.scalars(stmt).unique())

    def listar(
        self,
        *,
        data: date | None = None,
        data_de: date | None = None,
        data_ate: date | None = None,
        status: list[str] | None = None,
        priority: str | None = None,
        customer_id: int | None = None,
        sem_coordenada: bool | None = None,
        search: str | None = None,
        limite: int | None = None,
    ) -> list[Delivery]:
        stmt = self._ordenada()

        if data is not None:
            stmt = stmt.where(Delivery.scheduled_date == data)
        if data_de is not None:
            stmt = stmt.where(Delivery.scheduled_date >= data_de)
        if data_ate is not None:
            stmt = stmt.where(Delivery.scheduled_date <= data_ate)
        if status:
            stmt = stmt.where(Delivery.status.in_(status))
        if priority:
            stmt = stmt.where(Delivery.priority == priority)
        if customer_id is not None:
            stmt = stmt.where(Delivery.customer_id == customer_id)
        if sem_coordenada is True:
            stmt = stmt.where(Delivery.latitude.is_(None))
        elif sem_coordenada is False:
            stmt = stmt.where(Delivery.latitude.is_not(None))

        if search and search.strip():
            termo = f"%{search.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Delivery.address).like(termo),
                    func.lower(Delivery.recipient_name).like(termo),
                    func.lower(Delivery.description).like(termo),
                    func.lower(Delivery.order_number).like(termo),
                )
            )

        if limite:
            stmt = stmt.limit(limite)

        return list(self.session.scalars(stmt).unique())

    #: Ordem de exibicao da prioridade. Nao e alfabetica — ALTA vem antes de
    #: BAIXA e NORMAL, o que uma ordenacao por texto faria errado.
    _PESO_PRIORIDADE = case(
        {"URGENTE": 0, "ALTA": 1, "NORMAL": 2, "BAIXA": 3},
        value=Delivery.priority,
        else_=9,
    )

    def _ordenada(self) -> Select:
        # Data primeiro, prioridade depois: a tela e sempre "o que sai
        # hoje", e dentro do dia o urgente precisa aparecer no topo.
        return select(Delivery).order_by(
            Delivery.scheduled_date, self._PESO_PRIORIDADE, Delivery.id
        )

    def pendentes_para_planejar(self, data: date) -> list[Delivery]:
        """Entregas do dia que podem entrar num planejamento."""
        stmt = (
            select(Delivery)
            .where(
                Delivery.scheduled_date == data,
                Delivery.status == DeliveryStatus.PENDENTE.value,
            )
            .order_by(Delivery.id)
        )
        return list(self.session.scalars(stmt).unique())

    def para_geocodificar(self, limite: int = 50) -> list[Delivery]:
        stmt = (
            select(Delivery)
            .where(
                Delivery.address.is_not(None),
                Delivery.geocode_status.in_(
                    [GeocodeStatus.PENDENTE.value, GeocodeStatus.FALHOU.value]
                ),
            )
            .order_by(Delivery.scheduled_date, Delivery.id)
            .limit(limite)
        )
        return list(self.session.scalars(stmt).unique())

    def resumo(self, data: date | None = None) -> dict:
        stmt = select(Delivery.status, func.count()).group_by(Delivery.status)
        if data is not None:
            stmt = stmt.where(Delivery.scheduled_date == data)
        por_status = {s: c for s, c in self.session.execute(stmt)}

        stmt_sem = (
            select(func.count())
            .select_from(Delivery)
            .where(
                Delivery.latitude.is_(None),
                Delivery.status.notin_(
                    [DeliveryStatus.CANCELADA.value, DeliveryStatus.ENTREGUE.value]
                ),
            )
        )
        if data is not None:
            stmt_sem = stmt_sem.where(Delivery.scheduled_date == data)

        return {
            "total": sum(por_status.values()),
            "por_status": por_status,
            "sem_coordenada": self.session.scalar(stmt_sem) or 0,
        }

    def add(self, delivery: Delivery) -> Delivery:
        self.session.add(delivery)
        self.session.flush()
        return delivery

    # --- historico --------------------------------------------------------- #
    def registrar_evento(self, evento: DeliveryEvent) -> DeliveryEvent:
        self.session.add(evento)
        self.session.flush()
        return evento

    def eventos(self, delivery_id: int) -> list[DeliveryEvent]:
        stmt = (
            select(DeliveryEvent)
            .where(DeliveryEvent.delivery_id == delivery_id)
            .order_by(DeliveryEvent.created_at, DeliveryEvent.id)
        )
        return list(self.session.scalars(stmt))
