"""Ponto de entrada da API do Log Rotas.

Sistema de planejamento e execucao de rotas de entrega da
Britto Moveis e Corrimao.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import LogRotasError, logrotas_error_handler
from app.core.logging import configure_logging
from app.db.session import SessionLocal, engine
from app.services.manutencao import Agendador

logger = logging.getLogger(__name__)

settings = get_settings()
configure_logging(debug=settings.debug)

@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    """Liga o agendador da limpeza automatica junto com o servidor.

    Desligado com LIMPEZA_HORA=-1 (a suite de testes faz isso: ela sobe o
    app muitas vezes e nao pode apagar dado sozinha no meio de um teste).
    """
    agendador = None
    if settings.limpeza_hora >= 0:
        agendador = Agendador(SessionLocal)
        agendador.start()
        logger.info("Limpeza automatica agendada para %sh.", settings.limpeza_hora)
    yield
    if agendador:
        agendador.parar.set()


app = FastAPI(
    lifespan=ciclo_de_vida,
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


@app.middleware("http")
async def cabecalhos_de_seguranca(request: Request, call_next):
    """Cabecalhos que o navegador obedece, em toda resposta da API.

    - nosniff: o navegador nao "adivinha" que um JSON e HTML e o executa.
    - DENY: a API e o /docs nao podem ser embutidos em iframe de outro site.
    - no-store nas respostas da API: token e dado de cliente nao ficam no
      cache do navegador nem de proxy no caminho.
    - HSTS so com HTTPS de verdade (HSTS=true no .env): ligado em HTTP, o
      navegador guardaria uma promessa que o servidor nao cumpre.

    A Content-Security-Policy da TELA nao sai daqui: a tela e servida pelo
    nginx (producao) e pelo Vite (desenvolvimento). Ver docs/SEGURANCA.md.
    """
    resposta = await call_next(request)
    h = resposta.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.url.path.startswith("/api/"):
        h.setdefault("Cache-Control", "no-store")
    if settings.hsts:
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return resposta


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
