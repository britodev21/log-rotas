"""Leitura e alteracao da configuracao da empresa."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.company_settings import CompanySettings
from app.repositories.company_settings_repository import CompanySettingsRepository
from app.schemas.company_settings import CompanySettingsUpdate


class CompanySettingsService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = CompanySettingsRepository(session)

    def get(self) -> CompanySettings:
        settings = self.repo.get()
        if settings is None:
            raise NotFoundError(
                "O sistema ainda nao foi configurado. Conclua o primeiro acesso."
            )
        return settings

    def update(self, payload: CompanySettingsUpdate) -> CompanySettings:
        settings = self.get()
        for campo, valor in payload.model_dump(exclude_unset=True).items():
            if valor is None:
                continue
            setattr(settings, campo, valor.strip() if isinstance(valor, str) else valor)
        self.session.commit()
        return settings
