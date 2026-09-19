"""Modelos SQLAlchemy.

Importar tudo aqui garante que o Alembic enxergue todas as tabelas ao gerar
migrations (o autogenerate so ve o que esta registrado em Base.metadata).
"""

from app.db.base import Base
from app.models.company_settings import SETTINGS_ID, CompanySettings
from app.models.user import User

__all__ = ["SETTINGS_ID", "Base", "CompanySettings", "User"]
