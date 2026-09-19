"""Estimativa em linha reta — o fallback, sempre rotulado como tal."""

from __future__ import annotations

import math
from itertools import pairwise

from app.core.enums import MatrixSource
from app.routing.base import MatrixProvider, Matriz, Ponto, Trajeto

RAIO_TERRA_M = 6_371_000

#: Quanto o percurso por ruas costuma ser maior que a linha reta. Em malha
#: urbana ortogonal o fator gira em torno de 1.3; 1.35 e um meio-termo
#: conservador para Campo Grande.
#:
#: E um numero aproximado, nao medido na operacao da Britto. Por isso toda
#: matriz produzida aqui vem com `estimada=True` e a tela avisa.
FATOR_RUA = 1.35

#: Velocidade media urbana considerada, em km/h. Inclui semaforo e transito.
VELOCIDADE_KMH = 28.0


def distancia_haversine_m(a: Ponto, b: Ponto) -> float:
    """Distancia sobre a superficie da Terra, em metros."""
    lat1, lon1, lat2, lon2 = map(
        math.radians, (a.latitude, a.longitude, b.latitude, b.longitude)
    )
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * RAIO_TERRA_M * math.asin(math.sqrt(h))


class HaversineProvider(MatrixProvider):
    """Calculo local, sem rede, a partir das coordenadas.

    Existe por dois motivos:

    1. Ser a rede de seguranca quando o provedor de rotas esta fora do ar —
       melhor um planejamento aproximado e assumidamente aproximado do que
       nenhum planejamento.
    2. Permitir testar o otimizador sem depender de servico externo.

    O que ele NAO e: distancia de estrada. Linha reta nao atravessa rio, nao
    respeita mao unica e nao sabe que existe um viaduto. Todo resultado sai
    com `estimada=True`, e a interface e obrigada a dizer isso.
    """

    nome = "haversine"
    source = MatrixSource.HAVERSINE
    estimada = True

    def __init__(self, *, fator_rua: float = FATOR_RUA, velocidade_kmh: float = VELOCIDADE_KMH):
        self.fator_rua = fator_rua
        self.velocidade_ms = velocidade_kmh / 3.6

    def _par(self, a: Ponto, b: Ponto) -> tuple[int, int]:
        metros = distancia_haversine_m(a, b) * self.fator_rua
        segundos = metros / self.velocidade_ms if self.velocidade_ms else 0
        return round(metros), round(segundos)

    def matriz(self, pontos: list[Ponto]) -> Matriz:
        n = len(pontos)
        distancias = [[0] * n for _ in range(n)]
        duracoes = [[0] * n for _ in range(n)]

        for i in range(n):
            for j in range(i + 1, n):
                metros, segundos = self._par(pontos[i], pontos[j])
                # Simetrica, porque a linha reta e simetrica. E justamente
                # uma das razoes de ela nao servir como verdade: a rua real
                # nao e.
                distancias[i][j] = distancias[j][i] = metros
                duracoes[i][j] = duracoes[j][i] = segundos

        return Matriz(
            pontos=pontos,
            distancias=distancias,
            duracoes=duracoes,
            source=self.source,
            estimada=True,
            detalhe=(
                f"Estimativa em linha reta com fator {self.fator_rua:.2f} e "
                f"velocidade media de {self.velocidade_ms * 3.6:.0f} km/h. "
                "Nao e distancia de estrada."
            ),
            avisos=["Distancias e tempos sao estimados, nao medidos na malha viaria."],
        )

    def trajeto(self, pontos: list[Ponto]) -> Trajeto:
        distancia = 0
        duracao = 0
        for a, b in pairwise(pontos):
            metros, segundos = self._par(a, b)
            distancia += metros
            duracao += segundos

        return Trajeto(
            distancia_m=distancia,
            duracao_s=duracao,
            # Sem geometria: o mapa desenha a ligacao reta entre os pontos,
            # com tracejado, deixando obvio que aquele nao e o caminho real.
            geometria=None,
            source=self.source,
            estimada=True,
        )
