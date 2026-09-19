"""Base da operacao — de onde os veiculos saem e para onde voltam."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Identity, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.mixins import GeocodableMixin


class BaseLocation(Base, GeocodableMixin, TimestampMixin):
    """Centro de distribuicao, loja ou fabrica.

    A classe nao se chama `Base` para nao colidir com a base declarativa do
    SQLAlchemy; a tabela se chama `bases`.

    O modelo ja aceita varias bases embora a Britto provavelmente opere com
    uma so — loja e fabrica sao enderecos diferentes, e o custo de permitir
    varias agora e uma coluna `is_default`.
    """

    __tablename__ = "bases"
    __table_args__ = (
        *GeocodableMixin.geocode_constraints("bases"),
        {"comment": "Pontos de partida e retorno das rotas."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(String(500))

    # A base padrao e a pre-selecionada no planejador. O service garante que
    # exista no maximo uma marcada.
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BaseLocation id={self.id} name={self.name!r}>"
