"""Historico de mudancas de estado das entregas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DeliveryEvent(Base):
    """Registro imutavel de cada transicao de status.

    Logistica vive de comprovacao. "O motorista registrou cliente ausente as
    14h32, nesta coordenada" e informacao que a empresa vai precisar contra
    reclamacao — e que a coluna `status`, por ser sobrescrita, destroi.

    Append-only: nunca alterado, nunca apagado.
    """

    __tablename__ = "delivery_events"
    __table_args__ = (
        Index("ix_delivery_events_entrega", "delivery_id", "created_at"),
        {"comment": "Historico append-only das entregas."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)

    delivery_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("deliveries.id", ondelete="CASCADE"), nullable=False
    )
    route_stop_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("route_stops.id", ondelete="SET NULL")
    )

    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(String(500))

    actor_user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )

    # Onde o motorista estava quando registrou. Anulavel: o navegador so
    # libera geolocalizacao em contexto seguro, e nem sempre ha sinal.
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
