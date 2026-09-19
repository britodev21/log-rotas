"""Ponto de entrada da API do Log Rotas.

Sistema de planejamento e execucao de rotas de entrega da
Britto Moveis e Corrimao.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import LogRotasError, logrotas_error_handler
from app.core.logging import configure_logging
from app.db.session import engine

logger = logging.getLogger(__name__)

settings = get_settings()
configure_logging(debug=settings.debug)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "API do Log Rotas — planejamento e execucao de rotas de entrega.\n\n"
        "Autenticacao por Bearer token (JWT). Comece por POST /api/v1/setup "
        "na primeira execucao, depois por POST /api/v1/auth/login."
    ),
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json",
)

# CORS restrito as origens declaradas no .env. Curinga "*" nunca entra aqui:
# com credenciais habilitadas ele e recusado pelo navegador e, sem elas,
# abriria a API para qualquer site.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.add_exception_handler(LogRotasError, logrotas_error_handler)


@app.exception_handler(IntegrityError)
async def integrity_error_handler(_: Request, exc: IntegrityError) -> JSONResponse:
    """Rede de seguranca para constraints do banco.

    Uma violacao de unicidade que escapou da validacao do service e conflito
    (409), nao erro interno (500). A mensagem do banco nao vai para o cliente
    porque revelaria nomes de tabelas e colunas.
    """
    logger.warning("Violacao de integridade no banco: %s", exc.orig)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "erro": "conflito",
            "mensagem": "A operacao conflita com um registro existente.",
            "detalhes": {},
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Falha de banco de dados", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "erro": "banco_indisponivel",
            "mensagem": "Nao foi possivel acessar o banco de dados.",
            "detalhes": {},
        },
    )


@app.get("/health", tags=["Infraestrutura"], summary="Saude da aplicacao")
def health() -> dict[str, str]:
    """Verifica a API e a conexao com o banco."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        banco = "ok"
    except SQLAlchemyError:
        logger.exception("Health check falhou ao conectar no banco.")
        banco = "indisponivel"

    return {"status": "ok" if banco == "ok" else "degradado", "banco": banco}


app.include_router(api_router)
