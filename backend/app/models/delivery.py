"""Entrega — a unidade de trabalho da operacao."""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Time,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DeliveryStatus, Priority
from app.db.base import Base, TimestampMixin
from app.models.mixins import GeocodableMixin

_STATUS = ", ".join(f"'{s.value}'" for s in DeliveryStatus)
_PRIORIDADES = ", ".join(f"'{p.value}'" for p in Priority)


class Delivery(Base, GeocodableMixin, TimestampMixin):
    """Uma entrega a ser feita numa data.

    Tres decisoes que merecem explicacao:

    1. `customer_id` e ANULAVEL. Numa loja de moveis a maior parte da venda
       e avulsa: o cliente compra uma vez e nao volta tao cedo. Obrigar
       cadastro de cliente para lancar uma entrega criaria centenas de
       fichas de uso unico. A entrega carrega o proprio endereco.

    2. Peso, volume e comprimento sao TODOS opcionais, assim como no
       veiculo. Ainda nao se sabe o que limita a carga da Britto, e a regra
       do projeto e nao inventar numero. O otimizador so aplica a dimensao
       que estiver preenchida dos dois lados.

    3. `service_time_minutes` e anulavel e cai no padrao da empresa quando
       vazio. Esse e o parametro que mais pesa no planejamento de Campo
       Grande: com deslocamentos de 10 a 25 minutos, o que limita o dia da
       equipe e quanto tempo ela fica parada, nao quanto roda.
    """

    __tablename__ = "deliveries"
    __table_args__ = (
        *GeocodableMixin.geocode_constraints("deliveries"),
        CheckConstraint(f"status IN ({_STATUS})", name="status_valido"),
        CheckConstraint(f"priority IN ({_PRIORIDADES})", name="prioridade_valida"),
        CheckConstraint("weight_kg IS NULL OR weight_kg >= 0", name="peso_nao_negativo"),
        CheckConstraint("volume_m3 IS NULL OR volume_m3 >= 0", name="volume_nao_negativo"),
        CheckConstraint("length_m IS NULL OR length_m >= 0", name="comprimento_nao_negativo"),
        CheckConstraint("required_crew >= 1", name="equipe_minima"),
        CheckConstraint(
            "service_time_minutes IS NULL OR service_time_minutes > 0",
            name="tempo_servico_positivo",
        ),
        # Janela invertida (fim antes do inicio) e impossivel de satisfazer e
        # so seria descoberta na hora de otimizar, como "sem solucao".
        CheckConstraint(
            "time_window_start IS NULL OR time_window_end IS NULL "
            "OR time_window_start < time_window_end",
            name="janela_coerente",
        ),
        # A listagem e sempre por data + situacao; sem este indice ela varre
        # a tabela inteira a cada abertura da tela.
        Index("ix_deliveries_data_status", "scheduled_date", "status"),
        {"comment": "Entregas a serem planejadas e executadas."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)

    customer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("customers.id", ondelete="SET NULL"), index=True
    )

    # Identificacao vinda do sistema de vendas. Opcional ate existir
    # integracao; serve para a equipe cruzar entrega com pedido no balcao.
    order_number: Mapped[str | None] = mapped_column(String(40), index=True)
    invoice_number: Mapped[str | None] = mapped_column(String(40))

    recipient_name: Mapped[str | None] = mapped_column(String(160))
    recipient_phone: Mapped[str | None] = mapped_column(String(30))

    description: Mapped[str | None] = mapped_column(String(255))

    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    length_m: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    required_crew: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    service_time_minutes: Mapped[int | None] = mapped_column(Integer)

    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'NORMAL'")
    )

    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    time_window_start: Mapped[time | None] = mapped_column(Time)
    time_window_end: Mapped[time | None] = mapped_column(Time)

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PENDENTE'"), index=True
    )

    notes: Mapped[str | None] = mapped_column(String(500))

    customer = relationship("Customer", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Delivery id={self.id} status={self.status} data={self.scheduled_date}>"
