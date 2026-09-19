"""Hash de senha (Argon2id) e emissao/validacao de JWT.

Argon2id e o algoritmo recomendado atualmente para senhas. Usamos argon2-cffi
diretamente em vez de passlib porque passlib esta sem manutencao ativa e quebra
com versoes recentes do bcrypt.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.core.enums import TokenType

_hasher = PasswordHasher()


# --------------------------------------------------------------------------- #
# Senhas
# --------------------------------------------------------------------------- #
def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, plain_password)
    except VerifyMismatchError, VerificationError, InvalidHashError:
        return False
    return True


def password_needs_rehash(password_hash: str) -> bool:
    """True quando o hash foi gerado com parametros antigos do Argon2."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def _create_token(
    *,
    subject: int,
    role: str,
    token_version: int,
    token_type: TokenType,
    expires_delta: timedelta,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        # token_version permite revogar todos os tokens de um usuario
        # incrementando um inteiro na tabela users (troca de senha, demissao).
        "tv": token_version,
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(*, subject: int, role: str, token_version: int) -> str:
    settings = get_settings()
    return _create_token(
        subject=subject,
        role=role,
        token_version=token_version,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(*, subject: int, role: str, token_version: int) -> str:
    settings = get_settings()
    return _create_token(
        subject=subject,
        role=role,
        token_version=token_version,
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str, *, expected_type: TokenType) -> dict[str, Any]:
    """Decodifica e valida um token. Levanta jwt.PyJWTError em qualquer falha."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "iat", "sub", "type"]},
    )
    if payload.get("type") != expected_type.value:
        raise jwt.InvalidTokenError(
            f"Token do tipo '{payload.get('type')}', esperado '{expected_type.value}'."
        )
    return payload
