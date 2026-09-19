"""Acesso a dados de usuario.

Repositorio nao valida regra de negocio e nao faz commit — quem controla a
transacao e a camada de service, para que varias escritas caibam na mesma.
"""

from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    # --- leitura --- #
    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.strip().lower())
        return self.session.scalars(stmt).one_or_none()

    def count(self) -> int:
        return self.session.scalar(select(func.count()).select_from(User)) or 0

    def exists_any(self) -> bool:
        """Usado pelo primeiro acesso: o sistema ainda esta vazio?"""
        return self.session.scalar(select(select(User.id).limit(1).exists())) or False

    def email_taken(self, email: str, *, exclude_id: int | None = None) -> bool:
        stmt: Select[tuple[int]] = select(User.id).where(User.email == email.strip().lower())
        if exclude_id is not None:
            stmt = stmt.where(User.id != exclude_id)
        return self.session.scalar(stmt.limit(1)) is not None

    def list(
        self,
        *,
        role: str | None = None,
        active: bool | None = None,
        search: str | None = None,
    ) -> list[User]:
        stmt = select(User).order_by(User.name)
        if role is not None:
            stmt = stmt.where(User.role == role)
        if active is not None:
            stmt = stmt.where(User.active.is_(active))
        if search:
            termo = f"%{search.strip().lower()}%"
            stmt = stmt.where(func.lower(User.name).like(termo) | User.email.like(termo))
        return list(self.session.scalars(stmt))

    def count_active_admins(self, *, exclude_id: int | None = None) -> int:
        """Quantos ADMIN ativos existem — impede deixar o sistema sem dono."""
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.role == "ADMIN", User.active.is_(True))
        )
        if exclude_id is not None:
            stmt = stmt.where(User.id != exclude_id)
        return self.session.scalar(stmt) or 0

    # --- escrita --- #
    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()  # atribui o id sem encerrar a transacao
        return user
