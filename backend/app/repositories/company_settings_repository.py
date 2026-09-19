"""Acesso a configuracao da empresa (tabela de linha unica)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.company_settings import SETTINGS_ID, CompanySettings


class CompanySettingsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self) -> CompanySettings | None:
        return self.session.get(CompanySettings, SETTINGS_ID)

    def add(self, settings: CompanySettings) -> CompanySettings:
        self.session.add(settings)
        self.session.flush()
        return settings
