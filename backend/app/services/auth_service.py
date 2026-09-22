"""Autenticacao: login, emissao e renovacao de token, troca de senha."""

from __future__ import annotations

import logging
from functools import lru_cache

import jwt

from app.core.config import get_settings
from app.core.enums import TokenType
from app.core.errors import AuthenticationError, ValidationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.core.senha import exigir_senha_valida
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenPair

logger = logging.getLogger(__name__)

# Mensagem unica para "e-mail inexistente", "senha errada" e "usuario inativo".
# Diferenciar os casos entregaria a um atacante a lista de e-mails validos.
_CREDENCIAL_INVALIDA = "E-mail ou senha incorretos."


@lru_cache(maxsize=1)
def _hash_descartavel() -> str:
    """Hash usado para gastar tempo quando o e-mail nao existe.

    Sem isso, a resposta para um e-mail inexistente volta muito mais rapido do
    que para um e-mail valido com senha errada, e essa diferenca de tempo
    revela quais e-mails estao cadastrados.
    """
    return hash_password("senha-que-nao-pertence-a-ninguem")


class AuthService:
    def __init__(self, users: UserRepository) -> None:
        self.users = users

    # ------------------------------------------------------------------ #
    # Login
    # ------------------------------------------------------------------ #
    def authenticate(self, email: str, password: str) -> User:
        user = self.users.get_by_email(email)

        if user is None:
            verify_password(password, _hash_descartavel())
            raise AuthenticationError(_CREDENCIAL_INVALIDA)

        if not verify_password(password, user.password_hash):
            raise AuthenticationError(_CREDENCIAL_INVALIDA)

        if not user.active:
            logger.info("Login recusado: usuario %s esta inativo.", user.id)
            raise AuthenticationError(_CREDENCIAL_INVALIDA)

        # Aproveita o login para atualizar hashes gerados com parametros
        # antigos do Argon2 — o unico momento em que a senha em claro existe.
        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        return user

    # ------------------------------------------------------------------ #
    # Tokens
    # ------------------------------------------------------------------ #
    def issue_tokens(self, user: User) -> TokenPair:
        settings = get_settings()
        return TokenPair(
            access_token=create_access_token(
                subject=user.id, role=user.role, token_version=user.token_version
            ),
            refresh_token=create_refresh_token(
                subject=user.id, role=user.role, token_version=user.token_version
            ),
            expires_in=settings.access_token_expire_minutes * 60,
        )

    def resolve_token(self, token: str, *, expected_type: TokenType) -> User:
        """Valida o token e devolve o usuario, ou levanta AuthenticationError."""
        try:
            payload = decode_token(token, expected_type=expected_type)
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("Sessao expirada. Faca login novamente.") from exc
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Token invalido.") from exc

        try:
            user_id = int(payload["sub"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationError("Token invalido.") from exc

        user = self.users.get_by_id(user_id)
        if user is None or not user.active:
            raise AuthenticationError("Usuario sem acesso ao sistema.")

        # Revogacao: qualquer incremento de token_version derruba os tokens
        # emitidos antes dele (troca de senha, desligamento).
        if payload.get("tv") != user.token_version:
            raise AuthenticationError("Sessao encerrada. Faca login novamente.")

        return user

    def refresh(self, refresh_token: str) -> tuple[User, TokenPair]:
        user = self.resolve_token(refresh_token, expected_type=TokenType.REFRESH)
        return user, self.issue_tokens(user)

    # ------------------------------------------------------------------ #
    # Senha
    # ------------------------------------------------------------------ #
    def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise AuthenticationError("Senha atual incorreta.")
        if verify_password(new_password, user.password_hash):
            raise ValidationError("A nova senha precisa ser diferente da atual.")
        exigir_senha_valida(new_password, email=user.email, nome=user.name)

        user.password_hash = hash_password(new_password)
        # Derruba as outras sessoes: quem trocou a senha continua logado ao
        # receber o par de tokens novo, e qualquer sessao antiga para de valer.
        user.token_version += 1
