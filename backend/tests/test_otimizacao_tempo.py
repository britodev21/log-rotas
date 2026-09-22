"""O tempo que o otimizador grava como chegada e mesmo a chegada.

Direto no solver, sem banco e sem API: o que se verifica e o significado
do numero, que e o que o plano, a tela e a previsao ao vivo usam.
"""

from __future__ import annotations

from app.optimization import (
    JanelaHorario,
    OpcoesOtimizacao,
    OptimizationRequest,
    ParadaPlanejada,
    VeiculoDisponivel,
    resolver,
)

UMA_HORA = 3600


def _pedido(parada: ParadaPlanejada, ida_s: int = 600) -> OptimizationRequest:
    return OptimizationRequest(
        deposito=ParadaPlanejada(
            id="base", latitude=-20.46, longitude=-54.62, rotulo="Base", tempo_servico_s=0
        ),
        paradas=[parada],
        veiculos=[VeiculoDisponivel(id="v1", rotulo="Caminhao", jornada_s=12 * UMA_HORA)],
        duracoes=[[0, ida_s], [ida_s, 0]],
        distancias=[[0, 1000], [1000, 0]],
        opcoes=OpcoesOtimizacao(limite_tempo_s=2, inicio_turno_s=0),
    )


def _chegada(resultado) -> int:
    return resultado.rotas[0].paradas[0].chegada_estimada_s


def test_chegada_e_so_a_estrada_sem_o_servico_da_propria_parada() -> None:
    """Entrega a 10 min da base, com 1 h de instalacao, chega em 10 min.

    Estava chegando em 70: o otimizador somava o servico do destino, e o
    numero gravado como chegada era o FIM do servico.
    """
    parada = ParadaPlanejada(
        id="p1", latitude=-20.45, longitude=-54.61, rotulo="Cliente", tempo_servico_s=UMA_HORA
    )

    assert _chegada(resolver(_pedido(parada))) == 600


def test_janela_do_cliente_vale_para_a_chegada() -> None:
    """Cliente que só recebe o caminhão entre 1h e 1h05 depois do início.

    Com a janela valendo para a CHEGADA, cabe: chega em 1h, instala por 1 h.
    Com ela valendo para o FIM do serviço — como estava —, a instalação de
    1 h teria de terminar nesses 5 minutos, o que é impossível, e a entrega
    era dispensada do plano. Janela larga não distingue os dois modelos;
    esta, sim.
    """
    parada = ParadaPlanejada(
        id="p1", latitude=-20.45, longitude=-54.61, rotulo="Cliente",
        tempo_servico_s=UMA_HORA,
        janela=JanelaHorario(inicio_s=UMA_HORA, fim_s=UMA_HORA + 300),
    )

    resultado = resolver(_pedido(parada))

    assert resultado.rotas, "a entrega cabe e não pode ser dispensada"
    assert UMA_HORA <= _chegada(resultado) <= UMA_HORA + 300
