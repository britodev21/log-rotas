"""Gestao de usuarios pelo administrador."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.enums import Role
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.core.security import hash_password
from app.core.senha import exigir_senha_valida
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate, UserUpdate
from app.services.seguranca_service import SegurancaService

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)

    # --- leitura --- #
    def get(self, user_id: int) -> User:
        user = self.users.get_by_id(user_id)
        if user is None:
            raise NotFoundError("Usuario nao encontrado.")
        return user

    def list(
        self,
        *,
        role: Role | None = None,
        active: bool | None = None,
        search: str | None = None,
    ) -> list[User]:
        return self.users.list(role=role.value if role else None, active=active, search=search)

    # --- escrita --- #
    def create(self, payload: UserCreate, *, actor: User | None = None) -> User:
        if self.users.email_taken(payload.email):
            raise ConflictError(f"O e-mail {payload.email} ja esta cadastrado.")
        exigir_senha_valida(payload.password, email=payload.email, nome=payload.name)

        user = self.users.add(
            User(
                name=payload.name.strip(),
                email=payload.email,
                password_hash=hash_password(payload.password),
                role=payload.role.value,
                active=payload.active,
            )
        )
        SegurancaService(self.session).evento(
            "USUARIO_CRIADO", actor=actor, target=user, detalhe={"papel": user.role}
        )
        self.session.commit()
        logger.info("Usuario %s criado com papel %s.", user.email, user.role)
        return user

    def update(self, user_id: int, payload: UserUpdate, *, actor: User) -> User:
        user = self.get(user_id)
        dados = payload.model_dump(exclude_unset=True)

        if dados.get("name"):
            user.name = dados["name"].strip()

        novo_papel = dados.get("role")
        novo_ativo = dados.get("active")

        # Duas travas contra o sistema ficar sem administrador: um ADMIN nao
        # pode ser rebaixado nem desativado se for o ultimo ativo. Sem isso,
        # um clique deixa a empresa trancada para fora do proprio sistema.
        perde_admin = (
            user.role == Role.ADMIN.value
            and user.active
            and ((novo_papel is not None and novo_papel != Role.ADMIN) or novo_ativo is False)
        )
        if perde_admin and self.users.count_active_admins(exclude_id=user.id) == 0:
            raise ValidationError(
                "Este e o unico administrador ativo. Promova outro antes de alterar este."
            )

        eventos = SegurancaService(self.session)
        if novo_papel is not None and novo_papel.value != user.role:
            eventos.evento(
                "PAPEL_ALTERADO",
                actor=actor,
                target=user,
                detalhe={"de": user.role, "para": novo_papel.value},
            )
            user.role = novo_papel.value

        if novo_ativo is not None and novo_ativo != user.active:
            eventos.evento(
                "USUARIO_REATIVADO" if novo_ativo else "USUARIO_DESATIVADO",
                actor=actor,
                target=user,
            )
            user.active = novo_ativo
            if not novo_ativo:
                # Desativar precisa derrubar as sessoes abertas na hora; sem
                # isso o usuario segue usando o token ate ele expirar.
                user.token_version += 1

        self.session.commit()
        logger.info("Usuario %s atualizado por %s.", user.id, actor.id)
        return user

    def reset_password(self, user_id: int, new_password: str, *, actor: User) -> User:
        user = self.get(user_id)
        exigir_senha_valida(new_password, email=user.email, nome=user.name)
        user.password_hash = hash_password(new_password)
        user.token_version += 1
        SegurancaService(self.session).evento("SENHA_REDEFINIDA", actor=actor, target=user)
        self.session.commit()
        logger.info("Senha do usuario %s redefinida pelo admin %s.", user.id, actor.id)
        return user
