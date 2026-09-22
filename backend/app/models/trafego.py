"""Trechos com trânsito já consultados no Google."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Identity, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TrafficLeg(Base):
    """Tempo e distância de A até B, com o trânsito previsto para uma hora.

    Existe para recalcular o plano não custar de novo. Refazer o
    planejamento do mesmo dia — trocar um veículo, tirar uma entrega — só
    consulta o Google para os pares que ainda não foram consultados.

    Vale para UMA hora de partida: o trânsito das 8h não serve para as 18h.
    A limpeza diária apaga o que é de dias que já passaram.
    """

    __tablename__ = "trafego_trechos"
    __table_args__ = (
        Index("ux_trafego_trecho", "origem", "destino", "partida", unique=True),
        Index("ix_trafego_partida", "partida"),
        {"comment": "Tempo com transito entre dois pontos, por hora de partida."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    #: "lat,lon" com 5 casas (~1 m): dois pinos no mesmo lugar são o mesmo ponto.
    origem: Mapped[str] = mapped_column(String(24), nullable=False)
    destino: Mapped[str] = mapped_column(String(24), nullable=False)
    #: Hora cheia de partida pedida ao Google.
    partida: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duracao_s: Mapped[int] = mapped_column(Integer, nullable=False)
    distancia_m: Mapped[int] = mapped_column(Integer, nullable=False)
    consultado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
