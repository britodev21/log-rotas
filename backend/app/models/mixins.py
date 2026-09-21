"""Blocos de coluna reaproveitados por mais de uma tabela."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import GeocodePrecision, GeocodeStatus

_STATUS = ", ".join(f"'{s.value}'" for s in GeocodeStatus)
_PRECISOES = ", ".join(f"'{p.value}'" for p in GeocodePrecision)


class GeocodableMixin:
    """Endereco convertido em coordenada.

    Usado por toda entidade que tem endereco e vira parada no mapa: base,
    cliente e, na Fase 3, entrega.

    O bloco inteiro entra agora, embora a geocodificacao so seja implementada
    na Fase 4. O motivo nao e adiantar trabalho: e que sem `geocode_status`
    nao da para distinguir "ainda nao geocodifiquei" de "geocodifiquei e
    falhou" de "o administrador arrastou o pino no mapa" — e sem essa
    distincao a tela de revisao de enderecos nao existe. Adicionar depois
    exigiria migration na tabela que mais tera dados.
    """

    address: Mapped[str | None] = mapped_column(String(255))

    # Guardado so com digitos, como telefone e documento. Endereco brasileiro
    # digitado por extenso e a pior entrada possivel para geocodificacao;
    # CEP mais numero acerta muito mais.
    postal_code: Mapped[str | None] = mapped_column(String(8))

    # NUMERIC, nao float: coordenada e valor exato de identificacao, e a
    # precisao de 6 casas resolve cerca de 11 cm — mais do que suficiente
    # para encontrar um portao.
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))

    geocode_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'PENDENTE'")
    )
    geocode_precision: Mapped[str | None] = mapped_column(String(20))
    geocode_provider: Mapped[str | None] = mapped_column(String(40))
    geocode_error: Mapped[str | None] = mapped_column(String(255))
    geocoded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @classmethod
    def geocode_constraints(cls, tabela: str) -> tuple:
        """CHECKs do bloco de geocodificacao, nomeados por tabela."""
        from sqlalchemy import CheckConstraint

        return (
            CheckConstraint(f"geocode_status IN ({_STATUS})", name="geocode_status_valido"),
            CheckConstraint(
                f"geocode_precision IS NULL OR geocode_precision IN ({_PRECISOES})",
                name="geocode_precisao_valida",
            ),
            # Latitude e longitude andam juntas: uma sem a outra nao localiza
            # nada e seria um estado impossivel de interpretar depois.
            CheckConstraint(
                "(latitude IS NULL) = (longitude IS NULL)",
                name="coordenada_completa",
            ),
            CheckConstraint(
                "latitude IS NULL OR latitude BETWEEN -90 AND 90",
                name="latitude_valida",
            ),
            CheckConstraint(
                "longitude IS NULL OR longitude BETWEEN -180 AND 180",
                name="longitude_valida",
            ),
        )
