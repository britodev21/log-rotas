"""Contrato de geocodificacao.

Esta e a PORTA. O resto do sistema conhece apenas o que esta aqui — nunca o
Nominatim, nunca uma resposta HTTP, nunca uma chave de API.

O motivo e concreto: o Nominatim e gratuito e limitado a uma requisicao por
segundo, o que serve para comecar mas nao para uma operacao que dependa do
sistema. Trocar por Google, LocationIQ ou ViaCEP precisa ser escrever um
arquivo novo neste diretorio, nao caçar chamadas espalhadas pelo codigo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.core.enums import GeocodePrecision, GeocodeStatus


@dataclass(frozen=True)
class Candidato:
    """Uma possibilidade devolvida pelo provedor."""

    latitude: float
    longitude: float
    display_name: str
    precision: GeocodePrecision | None = None


@dataclass
class GeocodeResult:
    """Resultado de uma tentativa de geocodificacao.

    `status` distingue os quatro desfechos possiveis, e essa distincao e o
    que torna a fila de revisao possivel:

    OK             uma resposta confiavel
    AMBIGUO        varias respostas plausiveis — quem decide e o humano
    NAO_ENCONTRADO o provedor nao achou nada
    ERRO_PROVEDOR  falha de rede, limite, indisponibilidade

    A diferenca entre os dois ultimos importa: endereco nao encontrado exige
    corrigir o endereco; erro de provedor exige tentar de novo mais tarde.
    Tratar os dois como "falhou" faria a equipe reescrever enderecos que
    estavam certos.
    """

    status: str
    latitude: float | None = None
    longitude: float | None = None
    precision: GeocodePrecision | None = None
    normalized_address: str | None = None
    provider: str = ""
    error: str | None = None
    candidatos: list[Candidato] = field(default_factory=list)
    raw: dict | None = None

    @property
    def sucesso(self) -> bool:
        return self.status == GeocodeStatus.OK.value

    @classmethod
    def ok(
        cls,
        *,
        latitude: float,
        longitude: float,
        precision: GeocodePrecision | None,
        normalized_address: str | None,
        provider: str,
        raw: dict | None = None,
    ) -> GeocodeResult:
        return cls(
            status=GeocodeStatus.OK.value,
            latitude=latitude,
            longitude=longitude,
            precision=precision,
            normalized_address=normalized_address,
            provider=provider,
            raw=raw,
        )

    @classmethod
    def ambiguo(cls, candidatos: list[Candidato], *, provider: str) -> GeocodeResult:
        return cls(
            status=GeocodeStatus.AMBIGUO.value,
            provider=provider,
            candidatos=candidatos,
            error=f"{len(candidatos)} enderecos possiveis.",
        )

    @classmethod
    def nao_encontrado(cls, *, provider: str) -> GeocodeResult:
        return cls(
            status=GeocodeStatus.FALHOU.value,
            provider=provider,
            error="Endereco nao encontrado pelo provedor.",
        )

    @classmethod
    def erro(cls, mensagem: str, *, provider: str) -> GeocodeResult:
        return cls(status="ERRO_PROVEDOR", provider=provider, error=mensagem)


class GeocodingProvider(Protocol):
    """Quem sabe converter endereco em coordenada."""

    nome: str

    def geocode(self, endereco: str) -> GeocodeResult:
        """Converte um endereco. Nunca levanta excecao de rede.

        Falha de provedor vira um GeocodeResult com status ERRO_PROVEDOR:
        geocodificar cinquenta enderecos nao pode parar no primeiro timeout.
        """
        ...
