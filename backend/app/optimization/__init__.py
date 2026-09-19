"""Otimizacao de rotas.

Camada isolada: os contratos sao dataclasses puras e o motor nao conhece
banco nem HTTP. Trocar OR-Tools por outro solver e escrever um arquivo novo
aqui e mudar uma linha no runner.
"""

from app.optimization.contracts import (
    Demanda,
    JanelaHorario,
    OpcoesOtimizacao,
    OptimizationRequest,
    OptimizationResult,
    ParadaDispensada,
    ParadaPlanejada,
    ParadaResolvida,
    RotaResolvida,
    SolverStatus,
    VeiculoDisponivel,
)
from app.optimization.ortools_engine import OrToolsEngine
from app.optimization.runner import resolver

__all__ = [
    "Demanda",
    "JanelaHorario",
    "OpcoesOtimizacao",
    "OptimizationRequest",
    "OptimizationResult",
    "OrToolsEngine",
    "ParadaDispensada",
    "ParadaPlanejada",
    "ParadaResolvida",
    "RotaResolvida",
    "SolverStatus",
    "VeiculoDisponivel",
    "resolver",
]
