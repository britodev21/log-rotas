"""Repositorios — a unica camada que monta SQL.

Regras: nao validam negocio, nao fazem commit e nao levantam excecoes HTTP.
Devolvem modelos ou None e deixam a decisao para a camada de service.
"""

from app.repositories.cadastros_repository import (
    BaseLocationRepository,
    CustomerRepository,
    DriverRepository,
    VehicleRepository,
)
from app.repositories.company_settings_repository import CompanySettingsRepository
from app.repositories.crud import CrudRepository
from app.repositories.user_repository import UserRepository

__all__ = [
    "BaseLocationRepository",
    "CompanySettingsRepository",
    "CrudRepository",
    "CustomerRepository",
    "DriverRepository",
    "UserRepository",
    "VehicleRepository",
]
