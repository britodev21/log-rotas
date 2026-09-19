"""Agregador das rotas da versao 1 da API.

Prefixo /api/v1 desde o primeiro dia: quando o app do motorista existir em
versao instalada no celular, quebrar contrato sem versionar deixaria aparelhos
antigos sem funcionar.
"""

from fastapi import APIRouter

from app.api.v1 import auth, company_settings, setup, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(setup.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(company_settings.router)

__all__ = ["api_router"]
