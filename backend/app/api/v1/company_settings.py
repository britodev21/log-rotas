"""Configuracao da empresa."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import AdminUser, DbSession
from app.schemas.company_settings import CompanySettingsRead, CompanySettingsUpdate
from app.services.company_settings_service import CompanySettingsService

router = APIRouter(prefix="/configuracoes", tags=["Configuracoes"])


@router.get("", response_model=CompanySettingsRead, summary="Ler a configuracao")
def get_settings(session: DbSession, _: AdminUser) -> CompanySettingsRead:
    return CompanySettingsRead.model_validate(CompanySettingsService(session).get())


@router.patch("", response_model=CompanySettingsRead, summary="Alterar a configuracao")
def update_settings(
    payload: CompanySettingsUpdate, session: DbSession, _: AdminUser
) -> CompanySettingsRead:
    return CompanySettingsRead.model_validate(CompanySettingsService(session).update(payload))
