"""Planejamento e execucao: planos, rotas, paradas e itens de parada."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import (
    DeliveryStatus,
    FailureReason,
    MatrixSource,
    PlanStatus,
    RouteStatus,
    StopStatus,
    StopType,
)
from app.db.base import Base, TimestampMixin


def _lista(enum) -> str:
    return ", ".join(f"'{e.value}'" for e in enum)


class RoutePlan(Base, TimestampMixin):
    """O resultado de uma execucao do otimizador, ANTES de virar rota real.

    Esta tabela e o que sustenta o fluxo calcular -> revisar -> confirmar.
    Sem ela, o administrador clicaria em "calcular" e o sistema ja teria
    escrito rotas de verdade no banco, mudado o status das entregas e
    comprometido o dia — exatamente o que nao pode acontecer.

    Tambem guarda a matriz usada, sua origem e as estatisticas do solver.
    Isso torna o resultado auditavel: da para provar depois por que o
    sistema montou aquelas rotas, e com que qualidade de dado.
    """

    __tablename__ = "route_plans"
    __table_args__ = (
        CheckConstraint(f"status IN ({_lista(PlanStatus)})", name="status_valido"),
        CheckConstraint(
            f"matrix_source IN ({_lista(MatrixSource)})", name="fonte_matriz_valida"
        ),
        Index("ix_route_plans_data", "date", "status"),
        {"comment": "Resultado de uma otimizacao, ainda nao confirmado."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)

    base_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bases.id", ondelete="RESTRICT"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'RASCUNHO'")
    )

    # Quais entregas, veiculos e motoristas foram escolhidos. Guardado para
    # que o plano possa ser explicado meses depois, mesmo que um veiculo
    # tenha sido desativado nesse meio tempo.
    params: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))

    matrix_source: Mapped[str] = mapped_column(String(20), nullable=False)
    solver: Mapped[str | None] = mapped_column(String(40))
    solver_status: Mapped[str | None] = mapped_column(String(30))
    solver_time_ms: Mapped[int | None] = mapped_column(Integer)

    total_distance_m: Mapped[int | None] = mapped_column(Integer)
    total_duration_s: Mapped[int | None] = mapped_column(Integer)

    # Entregas que nao couberam, com o motivo. Nunca somem em silencio.
    unassigned: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"))

    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    routes = relationship(
        "Route", back_populates="plan", cascade="all, delete-orphan", lazy="selectin"
    )


class Route(Base, TimestampMixin):
    """A rota de um veiculo num dia."""

    __tablename__ = "routes"
    __table_args__ = (
        CheckConstraint(f"status IN ({_lista(RouteStatus)})", name="status_valido"),
        # A regra real nao e "uma rota por motorista por dia" — turnos
        # existem. E "uma em execucao por vez", e o banco garante isso.
        Index(
            "uq_routes_driver_iniciada",
            "driver_id",
            unique=True,
            postgresql_where=text("status = 'INICIADA'"),
        ),
        Index(
            "uq_routes_vehicle_iniciada",
            "vehicle_id",
            unique=True,
            postgresql_where=text("status = 'INICIADA'"),
        ),
        Index("ix_routes_data_status", "date", "status"),
        {"comment": "Rota de um veiculo num dia."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)

    route_plan_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("route_plans.id", ondelete="CASCADE")
    )
    base_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("bases.id", ondelete="RESTRICT"), nullable=False
    )
    vehicle_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("vehicles.id", ondelete="RESTRICT"), nullable=False
    )
    driver_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("drivers.id", ondelete="RESTRICT"), index=True
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'RASCUNHO'")
    )

    # Ordena turnos no mesmo dia.
    sequence_in_day: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )

    total_distance_m: Mapped[int | None] = mapped_column(Integer)
    estimated_duration_s: Mapped[int | None] = mapped_column(Integer)
    planned_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    planned_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Geometria do trajeto devolvida pelo provedor de rotas, em polyline.
    # Guardada para o mapa nao precisar recalcular a cada abertura — e para
    # a rota exibida ser exatamente a que foi planejada.
    geometry: Mapped[str | None] = mapped_column(String)

    plan = relationship("RoutePlan", back_populates="routes")
    base = relationship("BaseLocation", lazy="joined")
    vehicle = relationship("Vehicle", lazy="joined")
    driver = relationship("Driver", lazy="joined")
    stops = relationship(
        "RouteStop",
        back_populates="route",
        cascade="all, delete-orphan",
        order_by="RouteStop.sequence",
        lazy="selectin",
    )


class RouteStop(Base):
    """Uma visita fisica — nao uma entrega.

    A distincao importa: o motorista estaciona uma vez e pode resolver
    varias entregas ali (predio, condominio, galeria). Por isso a parada
    guarda chegada e saida, e o resultado fica em `route_stop_deliveries`.

    `stop_type` e `trip_number` custam duas colunas hoje e sao o que torna o
    retorno a base para recarregar implementavel depois, sem migracao
    destrutiva. O MVP so gera BASE_SAIDA -> ENTREGA* -> BASE_RETORNO com
    trip_number = 1.
    """

    __tablename__ = "route_stops"
    __table_args__ = (
        CheckConstraint(f"stop_type IN ({_lista(StopType)})", name="tipo_valido"),
        CheckConstraint(f"status IN ({_lista(StopStatus)})", name="status_valido"),
        CheckConstraint("sequence >= 0", name="sequencia_nao_negativa"),
        CheckConstraint("trip_number >= 1", name="viagem_minima"),
        # DEFERRABLE para permitir reordenar as paradas numa transacao sem
        # esbarrar na unicidade a cada passo intermediario.
        UniqueConstraint(
            "route_id",
            "sequence",
            name="sequencia_unica",
            deferrable=True,
            initially="DEFERRED",
        ),
        {"comment": "Paradas de uma rota, na ordem de execucao."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)

    route_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("routes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    stop_type: Mapped[str] = mapped_column(String(20), nullable=False)
    trip_number: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    label: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(255))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    estimated_arrival: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    distance_from_previous_m: Mapped[int | None] = mapped_column(Integer)
    duration_from_previous_s: Mapped[int | None] = mapped_column(Integer)
    service_time_s: Mapped[int | None] = mapped_column(Integer)

    arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    departed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PENDENTE'")
    )
    notes: Mapped[str | None] = mapped_column(String(500))

    route = relationship("Route", back_populates="stops")
    items = relationship(
        "RouteStopDelivery",
        back_populates="stop",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class RouteStopDelivery(Base):
    """A tentativa de entrega dentro de uma parada.

    Existe como tabela propria, e nao como `deliveries.route_stop_id`,
    porque a entrega nao entregue volta a ser planejada depois. Com chave
    estrangeira na entrega, o vinculo com a tentativa anterior seria
    sobrescrito e o historico sumiria — e logistica vive de comprovacao:
    "tentamos na terca, cliente ausente; tentamos na quinta, entregue".
    """

    __tablename__ = "route_stop_deliveries"
    __table_args__ = (
        CheckConstraint(f"status IN ({_lista(DeliveryStatus)})", name="status_valido"),
        CheckConstraint(
            f"failure_reason IS NULL OR failure_reason IN ({_lista(FailureReason)})",
            name="motivo_valido",
        ),
        UniqueConstraint("route_stop_id", "delivery_id", name="entrega_unica_na_parada"),
        {"comment": "Entregas resolvidas em cada parada."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)

    route_stop_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("route_stops.id", ondelete="CASCADE"), nullable=False
    )
    delivery_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sequence_in_stop: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PLANEJADA'")
    )

    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(30))
    receiver_name: Mapped[str | None] = mapped_column(String(160))
    notes: Mapped[str | None] = mapped_column(String(500))

    stop = relationship("RouteStop", back_populates="items")
    delivery = relationship("Delivery", lazy="joined")
