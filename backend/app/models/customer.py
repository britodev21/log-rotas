"""Cliente — quem recebe a entrega."""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Identity, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.mixins import GeocodableMixin


class Customer(Base, GeocodableMixin, TimestampMixin):
    """Cadastro de cliente, com endereco geocodificavel.

    Numa loja de moveis o cliente costuma ser pontual — compra uma vez e nao
    volta tao cedo. Por isso a entrega da Fase 3 vai poder existir sem
    cliente cadastrado, carregando o proprio endereco. Este cadastro serve a
    quem compra com frequencia (construtora, marcenaria, revenda) e evita
    redigitar endereco a cada pedido.
    """

    __tablename__ = "customers"
    __table_args__ = (
        *GeocodableMixin.geocode_constraints("customers"),
        # Unicidade PARCIAL: dois clientes nao podem ter o mesmo CPF/CNPJ,
        # mas varios podem ficar sem documento. Um UNIQUE comum aceitaria
        # varios NULL no Postgres, porem o indice parcial deixa a intencao
        # explicita e nao indexa as linhas sem documento.
        Index(
            "uq_customers_document",
            "document",
            unique=True,
            postgresql_where=text("document IS NOT NULL"),
        ),
        {"comment": "Clientes que recebem entregas."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)

    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))
    document: Mapped[str | None] = mapped_column(String(20))  # CPF ou CNPJ

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    notes: Mapped[str | None] = mapped_column(String(500))

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Customer id={self.id} name={self.name!r}>"
