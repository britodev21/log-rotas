"""Modelos SQLAlchemy.

Importar tudo aqui garante que o Alembic enxergue todas as tabelas ao gerar
migrations (o autogenerate so ve o que esta registrado em Base.metadata).
"""

from app.db.base import Base
from app.models.base_location import BaseLocation
from app.models.company_settings import SETTINGS_ID, CompanySettings
from app.models.customer import Customer
from app.models.delivery import Delivery
from app.models.delivery_event import DeliveryEvent
from app.models.driver import Driver
from app.models.geocode_cache import GeocodeCache
from app.models.manutencao import MaintenanceRun
from app.models.route import Route, RoutePlan, RouteStop, RouteStopDelivery
from app.models.route_position import RoutePosition
from app.models.seguranca import LoginAttempt, SecurityEvent
from app.models.user import User
from app.models.vehicle import Vehicle

__all__ = [
    "SETTINGS_ID",
    "Base",
    "BaseLocation",
    "CompanySettings",
    "Customer",
    "Delivery",
    "DeliveryEvent",
    "Driver",
    "GeocodeCache",
    "LoginAttempt",
    "MaintenanceRun",
    "Route",
    "RoutePlan",
    "RoutePosition",
    "RouteStop",
    "RouteStopDelivery",
    "SecurityEvent",
    "User",
    "Vehicle",
]
