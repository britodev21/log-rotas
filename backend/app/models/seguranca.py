"""Registro de segurança: tentativas de login e eventos sobre contas."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LoginAttempt(Base):
    """Cada tentativa de login, com sucesso ou não.

    É daqui que sai o bloqueio por tentativas — no banco, e não em memória,
    por dois motivos: um reinício do servidor não pode zerar a contagem de
    quem está tentando adivinhar uma senha, e com mais de um processo a
    memória de cada um veria só parte das tentativas.

    O e-mail é guardado como foi digitado (normalizado), exista a conta ou
    não. Bloquear só contas existentes revelaria quais existem.
    """

    __tablename__ = "login_attempts"
    __table_args__ = (
        Index("ix_login_attempts_email_hora", "email", "created_at"),
        Index("ix_login_attempts_ip_hora", "ip", "created_at"),
        {"comment": "Tentativas de login: base do bloqueio por tentativas e da auditoria."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45))
    sucesso: Mapped[bool] = mapped_column(Boolean, nullable=False)
    #: CREDENCIAL, INATIVO, BLOQUEADO, OK ou DESBLOQUEIO (liberação pelo admin,
    #: que zera a contagem da conta).
    motivo: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    user_agent: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SecurityEvent(Base):
    """O que aconteceu com contas e senhas, e quem fez.

    Responde perguntas que só aparecem depois do problema: quem promoveu
    este usuário a administrador? quando a senha do motorista foi trocada, e
    por quem? a conta foi bloqueada por tentativas?
    """

    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_hora", "created_at"),
        {"comment": "Eventos de segurança sobre contas: auditoria."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    #: Quem fez. Nulo quando foi o próprio sistema (bloqueio automático).
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    #: Sobre quem. Nulo em evento sobre e-mail sem conta.
    target_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    email: Mapped[str | None] = mapped_column(String(254))
    ip: Mapped[str | None] = mapped_column(String(45))
    detalhe: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
