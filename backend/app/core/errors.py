"""Excecoes de dominio e a traducao delas para respostas HTTP.

As camadas de service e repository levantam estas excecoes; elas nao conhecem
FastAPI nem codigos HTTP. A traducao acontece uma unica vez, nos handlers
registrados em main.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse


class LogRotasError(Exception):
    """Raiz de todas as excecoes de dominio."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "erro"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(LogRotasError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "nao_encontrado"


class ConflictError(LogRotasError):
    """Violacao de regra de unicidade ou de estado (ex.: e-mail ja cadastrado)."""

    status_code = status.HTTP_409_CONFLICT
    code = "conflito"


class ValidationError(LogRotasError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validacao"


class AuthenticationError(LogRotasError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "nao_autenticado"


class PermissionDeniedError(LogRotasError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "sem_permissao"


class InvalidStateTransitionError(LogRotasError):
    """Transicao de status proibida pela maquina de estados (Fases 3 e 9)."""

    status_code = status.HTTP_409_CONFLICT
    code = "transicao_invalida"


async def logrotas_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, LogRotasError)
    headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, AuthenticationError) else None
    return JSONResponse(
        status_code=exc.status_code,
        content={"erro": exc.code, "mensagem": exc.message, "detalhes": exc.details},
        headers=headers,
    )
