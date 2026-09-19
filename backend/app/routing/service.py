"""Orquestracao do calculo de distancia e tempo."""

from __future__ import annotations

import logging

from app.core.config import get_settings
from app.routing.base import MatrixProvider, Matriz, Ponto, Trajeto
from app.routing.haversine import HaversineProvider
from app.routing.osrm import OSRMIndisponivel, OSRMProvider

logger = logging.getLogger(__name__)


def construir_provider(nome: str | None = None) -> MatrixProvider:
    escolhido = (nome or get_settings().matrix_provider).lower()
    if escolhido == "osrm":
        return OSRMProvider()
    return HaversineProvider()


class RoutingService:
    """Entrega uma matriz, com ou sem o provedor principal disponivel.

    Se o OSRM falhar, cai para a estimativa em linha reta em vez de
    interromper o planejamento — mas o resultado vem marcado como estimado,
    com o motivo da queda, e essa marcacao atravessa o plano, a API e a
    tela.

    Um planejamento aproximado e assumidamente aproximado vale mais do que
    nenhum. Um planejamento aproximado apresentado como exato nao vale nada.
    """

    def __init__(
        self,
        provider: MatrixProvider | None = None,
        *,
        permitir_fallback: bool = True,
    ) -> None:
        self.provider = provider or construir_provider()
        self.fallback = HaversineProvider()
        self.permitir_fallback = permitir_fallback

    def matriz(self, pontos: list[Ponto]) -> Matriz:
        if len(pontos) < 2:
            raise ValueError("A matriz precisa de ao menos dois pontos.")

        try:
            return self.provider.matriz(pontos)
        except OSRMIndisponivel as exc:
            if not self.permitir_fallback:
                raise
            logger.warning("Provedor de rotas indisponivel, usando estimativa: %s", exc)
            matriz = self.fallback.matriz(pontos)
            matriz.avisos.insert(
                0,
                "O servico de rotas nao respondeu; os numeros abaixo sao estimativa "
                "em linha reta, nao distancia de estrada.",
            )
            matriz.detalhe = f"{matriz.detalhe} Motivo da queda: {exc}"
            return matriz

    def trajeto(self, pontos: list[Ponto]) -> Trajeto:
        if len(pontos) < 2:
            return Trajeto(0, 0, None, self.provider.source, self.provider.estimada)
        try:
            return self.provider.trajeto(pontos)
        except OSRMIndisponivel as exc:
            if not self.permitir_fallback:
                raise
            logger.warning("Trajeto indisponivel, usando estimativa: %s", exc)
            return self.fallback.trajeto(pontos)
