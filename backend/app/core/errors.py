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

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.headers = headers


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


class ServiceUnavailableError(LogRotasError):
    """Um provedor externo nao respondeu ou recusou a chamada.

    Separado de ValidationError de proposito: "o Google esta fora" e "o
    endereco esta errado" pedem acoes diferentes, e quem le a mensagem
    precisa saber qual das duas.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "servico_indisponivel"


class TooManyRequestsError(LogRotasError):
    """Tentativas demais: a pessoa precisa esperar.

    Leva o `Retry-After` em segundos — o navegador e qualquer cliente de API
    sabem ler, e a tela diz quanto falta em vez de um "tente mais tarde".
    """

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "tentativas_demais"

    def __init__(self, message: str, *, segundos: int, details: dict[str, Any] | None = None):
        super().__init__(
            message,
            details={**(details or {}), "tente_em_segundos": segundos},
            headers={"Retry-After": str(segundos)},
        )


class InvalidStateTransitionError(LogRotasError):
    """Transicao de status proibida pela maquina de estados (Fases 3 e 9)."""

    status_code = status.HTTP_409_CONFLICT
    code = "transicao_invalida"


async def logrotas_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, LogRotasError)
    headers = dict(exc.headers or {})
    if isinstance(exc, AuthenticationError):
        headers["WWW-Authenticate"] = "Bearer"
    return JSONResponse(
        status_code=exc.status_code,
        content={"erro": exc.code, "mensagem": exc.message, "detalhes": exc.details},
        headers=headers or None,
    )
