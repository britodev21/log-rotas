"""Modelos SQLAlchemy.

Importar tudo aqui garante que o Alembic enxergue todas as tabelas ao gerar
migrations (o autogenerate so ve o que esta registrado em Base.metadata).
"""

from app.db.base import Base
from app.models.base_location import BaseLocation
from app.models.company_settings import SETTINGS_ID, CompanySettings
from app.models.customer import Customer
from app.models.driver import Driver
from app.models.user import User
from app.models.vehicle import Vehicle

__all__ = [
    "SETTINGS_ID",
    "Base",
    "BaseLocation",
    "CompanySettings",
    "Customer",
    "Driver",
    "User",
    "Vehicle",
]
