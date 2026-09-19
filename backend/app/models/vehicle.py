"""Veiculo da frota."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Identity,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Vehicle(Base, TimestampMixin):
    """Veiculo, com capacidade tipada em vez de um numero generico.

    "Capacidade = 1000" e ambiguo para o otimizador: ele precisa saber a
    unidade. Por isso as dimensoes sao separadas — e TODAS opcionais.

    O motivo de serem opcionais e honesto: ainda nao se sabe o que limita a
    carga da Britto. Moveis ocupam volume, corrimao de 6 metros e limitado
    por comprimento, e nenhum dos dois necessariamente pesa. Cada dimensao
    preenchida pode virar uma restricao no solver da Fase 6; as vazias sao
    simplesmente ignoradas. Custo de estar errado sobre qual importa: uma
    coluna nula.
    """

    __tablename__ = "vehicles"
    __table_args__ = (
        CheckConstraint(
            "capacity_weight_kg IS NULL OR capacity_weight_kg > 0",
            name="peso_positivo",
        ),
        CheckConstraint(
            "capacity_volume_m3 IS NULL OR capacity_volume_m3 > 0",
            name="volume_positivo",
        ),
        CheckConstraint(
            "capacity_length_m IS NULL OR capacity_length_m > 0",
            name="comprimento_positivo",
        ),
        CheckConstraint("max_stops IS NULL OR max_stops > 0", name="paradas_positivas"),
        CheckConstraint("crew_size >= 1", name="equipe_minima"),
        {"comment": "Frota disponivel para as rotas."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)

    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # Normalizada pela aplicacao: sem hifen, em maiusculas. A CHECK garante
    # que nenhum outro caminho grave diferente.
    plate: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    model: Mapped[str | None] = mapped_column(String(80))

    capacity_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    capacity_volume_m3: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    capacity_length_m: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    max_stops: Mapped[int | None] = mapped_column(Integer)

    # Quantas pessoas saem neste veiculo. A Britto informou entregas que
    # exigem ate quatro; a restricao de equipe entra no solver mais adiante,
    # mas o dado precisa existir para ser coletado desde ja.
    crew_size: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    notes: Mapped[str | None] = mapped_column(String(500))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Vehicle id={self.id} plate={self.plate!r}>"
