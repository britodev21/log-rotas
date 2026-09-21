"""Posicoes do veiculo durante a execucao de uma rota."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RoutePosition(Base):
    """Um ponto do GPS do celular do motorista, com a rota em andamento.

    Duas horas, de proposito:

    - `recorded_at` e a hora do APARELHO, quando o GPS mediu. E ela que
      conta onde o caminhao estava e quando.
    - `received_at` e a hora do SERVIDOR, quando o ponto chegou.

    A diferenca entre as duas e o que separa "o caminhao esta parado" de "o
    celular ficou sem sinal e mandou tudo de uma vez quando voltou". Com uma
    hora so, as duas situacoes seriam indistinguiveis no painel.

    Volume: um ponto a cada ~10 s da uma ordem de 3.600 linhas por rota de
    10 horas. Irrelevante para o PostgreSQL nos proximos anos da Britto, mas
    nao infinito — a limpeza periodica esta registrada em docs/LIMITACOES.md.
    """

    __tablename__ = "route_positions"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_valida"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_valida"),
        CheckConstraint("accuracy_m IS NULL OR accuracy_m >= 0", name="precisao_valida"),
        CheckConstraint("speed_mps IS NULL OR speed_mps >= 0", name="velocidade_valida"),
        CheckConstraint(
            "heading_deg IS NULL OR (heading_deg >= 0 AND heading_deg < 360)",
            name="direcao_valida",
        ),
        # A consulta quente e "a ultima posicao de cada rota em andamento".
        Index("ix_route_positions_rota_hora", "route_id", "recorded_at"),
        {"comment": "Rastro do GPS do motorista durante a execucao da rota."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    route_id: Mapped[int] = mapped_column(
        ForeignKey("routes.id", ondelete="CASCADE"), nullable=False
    )
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6), nullable=False)
    #: Raio de incerteza informado pelo aparelho, em metros. GPS de celular
    #: em area aberta fica em 5-15 m; dentro de galpao passa de 100.
    accuracy_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 1))
    speed_mps: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    heading_deg: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
