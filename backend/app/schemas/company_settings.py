"""Schemas da configuracao da empresa."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class CompanySettingsUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=2, max_length=160)
    document: str | None = Field(default=None, max_length=20)
    phone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=255)
    timezone: str | None = Field(default=None, max_length=64)
    default_stop_service_minutes: int | None = Field(default=None, ge=1, le=1440)


class CompanySettingsRead(ORMModel):
    id: int
    company_name: str
    document: str | None
    phone: str | None
    email: str | None
    timezone: str
    default_stop_service_minutes: int
    created_at: datetime
    updated_at: datetime
