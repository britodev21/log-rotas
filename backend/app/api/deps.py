"""Dependencias compartilhadas pelos endpoints.

E aqui que autenticacao e autorizacao entram no fluxo HTTP. Nenhum endpoint
decodifica token ou confere papel por conta propria: todos declaram a
dependencia correspondente, para que nao exista rota protegida por engano.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.enums import Role, TokenType
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService

DbSession = Annotated[Session, Depends(get_db)]

# auto_error=False para que a ausencia de header caia na nossa excecao de
# dominio, com o mesmo formato de resposta do resto da API.
_bearer = HTTPBearer(auto_error=False, description="Token JWT de acesso.")


def get_auth_service(session: DbSession) -> AuthService:
    return AuthService(UserRepository(session))


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_current_user(
    auth: AuthServiceDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Autenticacao necessaria.")
    return auth.resolve_token(credentials.credentials, expected_type=TokenType.ACCESS)


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role):
    """Fabrica de dependencia que exige um dos papeis informados."""
    permitidos = {r.value for r in roles}

    def _verificar(user: CurrentUser) -> User:
        if user.role not in permitidos:
            raise PermissionDeniedError("Seu perfil nao tem permissao para esta operacao.")
        return user

    return _verificar


AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]
DriverUser = Annotated[User, Depends(require_roles(Role.MOTORISTA))]
