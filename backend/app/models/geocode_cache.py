"""Cache de geocodificacao."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, Numeric, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GeocodeCache(Base):
    """Resultado de geocodificacao guardado por endereco normalizado.

    Existe por uma restricao concreta: o Nominatim permite UMA requisicao
    por segundo. Sem cache, importar duzentos enderecos levaria mais de tres
    minutos toda vez, e reconsultar o mesmo endereco a cada edicao seria
    desperdicio do recurso mais escasso do sistema.

    A chave e o hash do endereco normalizado. Nao ha vinculo com cliente
    nem entrega: endereco postal e dado publico, e amarrar o cache a um
    registro impediria o reuso, que e justamente o ponto.
    """

    __tablename__ = "geocode_cache"
    __table_args__ = ({"comment": "Enderecos ja convertidos em coordenada."},)

    address_hash: Mapped[str] = mapped_column(String(64), primary_key=True)

    normalized_address: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    precision: Mapped[str | None] = mapped_column(String(20))
    display_name: Mapped[str | None] = mapped_column(String(400))

    # Resposta bruta do provedor: permite reinterpretar resultados antigos
    # se a leitura da precisao mudar, sem reconsultar.
    raw: Mapped[dict | None] = mapped_column(JSONB)

    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
