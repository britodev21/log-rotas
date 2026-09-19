"""Execucao do solver fora do laco de eventos."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturoExpirado

from app.optimization.contracts import (
    OptimizationRequest,
    OptimizationResult,
    SolverStatus,
)
from app.optimization.ortools_engine import OrToolsEngine

logger = logging.getLogger(__name__)

#: Folga sobre o limite do proprio solver. Ele respeita o tempo que recebe;
#: esta margem cobre a montagem do modelo e a leitura da solucao.
FOLGA_S = 20

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="solver")


def resolver(pedido: OptimizationRequest) -> OptimizationResult:
    """Roda o solver numa thread separada, com teto de tempo.

    Duas razoes para nao rodar direto:

    1. O solver e CPU-bound e seguraria a requisicao inteira. O OR-Tools
       libera o GIL na parte em C++, entao uma thread resolve.
    2. Sem teto, um problema mal condicionado deixaria a requisicao pendurada
       ate o navegador desistir — e o usuario nao saberia se travou ou se
       ainda esta calculando.

    Se um dia o volume crescer, este e o unico arquivo que muda para virar
    fila com worker.
    """
    motor = OrToolsEngine()
    teto = pedido.opcoes.limite_tempo_s + FOLGA_S

    futuro = _executor.submit(motor.resolver, pedido)
    try:
        return futuro.result(timeout=teto)
    except FuturoExpirado:
        futuro.cancel()
        logger.error("Otimizacao excedeu %ss e foi interrompida.", teto)
        return OptimizationResult(
            status=SolverStatus.TEMPO_ESGOTADO,
            mensagem=(
                f"O calculo passou de {teto} segundos e foi interrompido. "
                "Tente com menos entregas ou aumente o limite de tempo."
            ),
            solver=motor.nome,
            tempo_ms=teto * 1000,
        )
    except Exception as exc:  # pragma: no cover - rede de seguranca
        logger.exception("Falha inesperada no motor de otimizacao")
        return OptimizationResult(
            status=SolverStatus.ERRO,
            mensagem=f"Falha ao calcular as rotas: {exc}",
            solver=motor.nome,
        )
