"""Repositorios dos cadastros da Fase 3."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.base_location import BaseLocation
from app.models.customer import Customer
from app.models.driver import Driver
from app.models.vehicle import Vehicle
from app.repositories.crud import CrudRepository


class BaseLocationRepository(CrudRepository[BaseLocation]):
    campos_busca = ("name", "address")

    def __init__(self, session: Session) -> None:
        super().__init__(session, BaseLocation)

    def padrao(self) -> BaseLocation | None:
        stmt = select(BaseLocation).where(BaseLocation.is_default.is_(True))
        return self.session.scalars(stmt).first()

    def limpar_padrao(self, *, exceto_id: int | None = None) -> None:
        """Desmarca a base padrao atual.

        Feito em um UPDATE unico em vez de carregar e alterar objeto por
        objeto: e a operacao que garante a regra "no maximo uma padrao", e
        quanto menos passos entre a leitura e a escrita, menor a janela para
        duas ficarem marcadas.
        """
        stmt = update(BaseLocation).where(BaseLocation.is_default.is_(True))
        if exceto_id is not None:
            stmt = stmt.where(BaseLocation.id != exceto_id)
        self.session.execute(stmt.values(is_default=False))


class VehicleRepository(CrudRepository[Vehicle]):
    campos_busca = ("name", "plate", "model")

    def __init__(self, session: Session) -> None:
        super().__init__(session, Vehicle)


class DriverRepository(CrudRepository[Driver]):
    campos_busca = ("name", "phone", "license_number")

    def __init__(self, session: Session) -> None:
        super().__init__(session, Driver)

    def por_usuario(self, user_id: int) -> Driver | None:
        stmt = select(Driver).where(Driver.user_id == user_id)
        return self.session.scalars(stmt).first()


class CustomerRepository(CrudRepository[Customer]):
    campos_busca = ("name", "phone", "address", "document")

    def __init__(self, session: Session) -> None:
        super().__init__(session, Customer)
