"""Contrato de calculo de distancia e tempo.

Esta e a PORTA do modulo de routing. O otimizador consome `Matriz` e nunca
sabe se ela veio da malha viaria real ou de uma estimativa em linha reta.

Mas a matriz CARREGA essa informacao, e ela e propagada ate a tela. Essa e a
diferenca entre estimar e mentir: o sistema pode trabalhar com aproximacao,
desde que diga que e aproximacao.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.core.enums import MatrixSource


@dataclass(frozen=True)
class Ponto:
    """Um lugar no mapa, com um identificador do dominio."""

    id: str
    latitude: float
    longitude: float
    rotulo: str = ""


@dataclass
class Matriz:
    """Distancias e duracoes entre todos os pares de pontos.

    `distancias[i][j]` = metros de i ate j.
    `duracoes[i][j]`   = segundos de i ate j.

    Nao e simetrica: mao unica e conversao proibida fazem a ida ser
    diferente da volta, e tratar como simetrica produziria rota que o
    motorista nao consegue executar.
    """

    pontos: list[Ponto]
    distancias: list[list[int]]
    duracoes: list[list[int]]
    source: MatrixSource
    #: Verdadeiro quando os numeros sao estimativa, nao medicao de estrada.
    #: Propagado ate a interface — ver docs/LIMITACOES.md.
    estimada: bool
    detalhe: str = ""
    avisos: list[str] = field(default_factory=list)

    @property
    def tamanho(self) -> int:
        return len(self.pontos)

    def indice(self, ponto_id: str) -> int:
        for i, p in enumerate(self.pontos):
            if p.id == ponto_id:
                return i
        raise KeyError(f"Ponto {ponto_id} nao esta na matriz.")


@dataclass
class Trajeto:
    """O caminho desenhavel entre dois ou mais pontos."""

    distancia_m: int
    duracao_s: int
    #: Polyline codificada (precisao 5), pronta para o Leaflet desenhar.
    geometria: str | None
    source: MatrixSource
    estimada: bool


class MatrixProvider(Protocol):
    """Quem sabe calcular distancia e tempo entre pontos."""

    nome: str
    source: MatrixSource
    estimada: bool

    def matriz(self, pontos: list[Ponto]) -> Matriz:
        """Matriz completa entre todos os pares."""
        ...

    def trajeto(self, pontos: list[Ponto]) -> Trajeto:
        """Caminho passando pelos pontos na ordem dada."""
        ...
