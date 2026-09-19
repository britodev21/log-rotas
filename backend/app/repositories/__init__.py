"""Repositorios — a unica camada que monta SQL.

Regras: nao validam negocio, nao fazem commit e nao levantam excecoes HTTP.
Devolvem modelos ou None e deixam a decisao para a camada de service.
"""

from app.repositories.company_settings_repository import CompanySettingsRepository
from app.repositories.user_repository import UserRepository

__all__ = ["CompanySettingsRepository", "UserRepository"]
