"""Registro das execuções de manutenção (limpeza automática)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MaintenanceRun(Base):
    """Uma execução da limpeza: quando, o que apagou e quem pediu.

    Existe para a pergunta "a limpeza está rodando?" ter resposta na tela,
    e não no log de um servidor que ninguém abre. E para o agendador saber
    se a limpeza de hoje já aconteceu, mesmo depois de o servidor reiniciar.
    """

    __tablename__ = "maintenance_runs"
    __table_args__ = (
        Index("ix_maintenance_runs_inicio", "iniciada_em"),
        {"comment": "Execucoes da limpeza automatica de dados antigos."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    #: AGENDADA (o próprio servidor, no horário) ou MANUAL (alguém pediu).
    origem: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    iniciada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    terminada_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    #: Linhas apagadas por tipo de dado.
    resultado: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    erro: Mapped[str | None] = mapped_column(String(500))
