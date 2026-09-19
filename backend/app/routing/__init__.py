"""Distancia e tempo entre pontos.

Porta e adaptadores. Quem consome fala com `RoutingService` e recebe uma
`Matriz` que carrega a propria origem — OSRM (malha viaria real) ou
HAVERSINE (estimativa em linha reta). Essa marcacao atravessa o sistema ate
a tela: o Log Rotas pode trabalhar com aproximacao, desde que diga que e
aproximacao.
"""

from app.routing.base import MatrixProvider, Matriz, Ponto, Trajeto
from app.routing.haversine import HaversineProvider, distancia_haversine_m
from app.routing.osrm import OSRMIndisponivel, OSRMProvider
from app.routing.service import RoutingService, construir_provider

__all__ = [
    "HaversineProvider",
    "MatrixProvider",
    "Matriz",
    "OSRMIndisponivel",
    "OSRMProvider",
    "Ponto",
    "RoutingService",
    "Trajeto",
    "construir_provider",
    "distancia_haversine_m",
]
