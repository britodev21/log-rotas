"""Configuracao da empresa — linha unica.

O Log Rotas NAO e multi-tenant: e a aplicacao da Britto Moveis e Corrimao.
Esta tabela guarda o que antes seria a tabela `companies`, sem o custo de
carregar company_id em todas as outras tabelas.

A CHECK (id = 1) e o que garante que a tabela nunca tenha uma segunda linha.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Integer, SmallInteger, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

SETTINGS_ID = 1


class CompanySettings(Base, TimestampMixin):
    __tablename__ = "company_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="linha_unica"),
        CheckConstraint("default_stop_service_minutes > 0", name="tempo_parada_positivo"),
        {"comment": "Dados e preferencias da empresa. Sempre uma unica linha."},
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)

    company_name: Mapped[str] = mapped_column(String(160), nullable=False)
    document: Mapped[str | None] = mapped_column(String(20))  # CNPJ
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(255))

    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'America/Campo_Grande'")
    )

    # Tempo padrao de permanencia numa parada, usado pelo planejador quando a
    # entrega nao informa o seu. Valor inicial e um chute a ser calibrado com
    # dados reais da operacao — ver docs/LIMITACOES.md.
    default_stop_service_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("60")
    )

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<CompanySettings {self.company_name!r}>"
