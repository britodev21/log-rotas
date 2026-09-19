"""Motorista — o perfil operacional de quem dirige."""

from __future__ import annotations

from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Identity, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Driver(Base, TimestampMixin):
    """Nao confundir com User.

    `User` e quem faz login; `Driver` e quem aparece no planejamento e leva a
    carga. Sao coisas diferentes, e `user_id` e ANULAVEL de proposito:

    - a empresa pode cadastrar o motorista antes de criar o acesso dele;
    - motorista terceirizado pode nunca ter login e ainda assim precisar
      aparecer numa rota.

    Forcar a existencia de um usuario impediria os dois casos, que sao reais
    numa operacao pequena.
    """

    __tablename__ = "drivers"
    __table_args__ = ({"comment": "Motoristas que executam as rotas."},)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)

    # ondelete SET NULL: apagar o acesso nao pode apagar o historico do
    # motorista, que esta amarrado as rotas que ele ja executou.
    user_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="SET NULL"),
        unique=True,
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    document: Mapped[str | None] = mapped_column(String(20))  # CPF
    license_number: Mapped[str | None] = mapped_column(String(20))  # CNH
    license_expires_at: Mapped[date | None] = mapped_column(Date)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    notes: Mapped[str | None] = mapped_column(String(500))

    user = relationship("User", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Driver id={self.id} name={self.name!r}>"
