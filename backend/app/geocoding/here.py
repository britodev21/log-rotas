"""Adaptador da Geocoding and Search API da HERE.

Alternativa ao Google para o mesmo problema: achar o NUMERO, que o
OpenStreetMap nao tem em Campo Grande (ver app/services/precisao.py).

Existe separado porque a HERE tem plano gratuito com cota diaria, enquanto
o Google cobra desde a primeira consulta acima do credito. Para uma
operacao do tamanho da Britto a cota gratuita tende a sobrar, e comecar sem
fatura e uma vantagem real. A contrapartida e cobertura: a base do Google
costuma ser mais completa no Brasil, e a diferenca aparece justamente em
loteamento novo e chacara — que e onde o Log Rotas mais sofre.

Nao ha como decidir entre os dois no escuro. Configure um, rode uma semana
de enderecos de verdade e olhe quantos caem na fila de conferencia.

Para usar:

    GEOCODING_PROVIDER=here
    GEOCODING_PROVIDER_KEY=<a chave>

AVISO DE HONESTIDADE: escrito e testado contra respostas gravadas, nao
contra a API real — nao ha chave disponivel aqui. A leitura das respostas
tem teste; a conversa de rede com a HERE nao foi exercitada. Confira um
endereco conhecido na tela antes de confiar.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings
from app.core.enums import GeocodePrecision
from app.geocoding.base import Candidato, GeocodeResult

logger = logging.getLogger(__name__)

URL = "https://geocode.search.hereapi.com/v1/geocode"

#: `resultType` da HERE traduzido para o que o planejamento precisa saber.
_PRECISAO = {
    "houseNumber": GeocodePrecision.EXATO,
    "street": GeocodePrecision.RUA,
    "intersection": GeocodePrecision.RUA,
    "postalCodePoint": GeocodePrecision.RUA,
    "addressBlock": GeocodePrecision.BAIRRO,
    "locality": GeocodePrecision.BAIRRO,
    "administrativeArea": GeocodePrecision.CIDADE,
}


def _precisao(item: dict) -> GeocodePrecision | None:
    """Traduz o tipo do resultado, com uma ressalva que importa.

    A HERE distingue `houseNumberType: "PA"` (point address — o endereco
    esta na base dela) de `"interpolated"` (ela sabe os numeros das pontas
    da quadra e estimou o resto).

    Interpolado costuma cair perto, e perto nao e o portao. Fica como RUA e
    pede confirmacao: melhor uma conferencia a mais que uma entrega na casa
    errada.
    """
    tipo = item.get("resultType")
    if tipo == "houseNumber" and item.get("houseNumberType") == "interpolated":
        return GeocodePrecision.RUA
    return _PRECISAO.get(tipo)


class HereProvider:
    """Geocodificacao pela HERE."""

    nome = "here"

    def __init__(self, *, chave: str | None = None) -> None:
        self.chave = chave or get_settings().geocoding_provider_key
        if not self.chave:
            raise ValueError(
                "GEOCODING_PROVIDER=here exige GEOCODING_PROVIDER_KEY no .env."
            )

    def buscar(self, endereco: str, limite: int = 5) -> list[Candidato]:
        resultado = self.geocode(endereco)
        if resultado.candidatos:
            return resultado.candidatos[:limite]
        if resultado.sucesso:
            return [
                Candidato(
                    latitude=resultado.latitude,
                    longitude=resultado.longitude,
                    display_name=resultado.normalized_address or endereco,
                    precision=resultado.precision,
                )
            ]
        return []

    def geocode(self, endereco: str) -> GeocodeResult:
        if not endereco or not endereco.strip():
            return GeocodeResult.nao_encontrado(provider=self.nome)

        params = {
            "q": endereco.strip(),
            "apiKey": self.chave,
            # Sem isto "Rua 14 de Julho" casa com endereco em Portugal.
            "in": "countryCode:BRA",
            "lang": "pt-BR",
            "limit": 5,
        }

        try:
            with httpx.Client(timeout=12.0) as cliente:
                resposta = cliente.get(URL, params=params)
                resposta.raise_for_status()
                dados = resposta.json()
        except httpx.HTTPStatusError as exc:
            codigo = exc.response.status_code
            logger.warning("HERE respondeu %s", codigo)
            if codigo == 429:
                return GeocodeResult.erro(
                    "A cota diaria da HERE acabou.", provider=self.nome
                )
            if codigo in (401, 403):
                return GeocodeResult.erro(
                    "A HERE recusou a requisicao. Confira a chave de API.",
                    provider=self.nome,
                )
            return GeocodeResult.erro(
                f"O servico de geocodificacao respondeu {codigo}.", provider=self.nome
            )
        except httpx.HTTPError:
            return GeocodeResult.erro(
                "Nao foi possivel consultar o servico de geocodificacao.",
                provider=self.nome,
            )
        except ValueError:
            return GeocodeResult.erro(
                "Resposta invalida do servico de geocodificacao.", provider=self.nome
            )

        itens = dados.get("items") or []
        if not itens:
            return GeocodeResult.nao_encontrado(provider=self.nome)

        candidatos = [
            Candidato(
                latitude=i["position"]["lat"],
                longitude=i["position"]["lng"],
                display_name=(i.get("address") or {}).get("label") or i.get("title", ""),
                precision=_precisao(i),
            )
            for i in itens
            if i.get("position")
        ]
        if not candidatos:
            return GeocodeResult.nao_encontrado(provider=self.nome)

        primeiro = itens[0]
        precisao = _precisao(primeiro)

        if len(candidatos) > 1 and precisao is not GeocodePrecision.EXATO:
            return GeocodeResult.ambiguo(candidatos, provider=self.nome)

        return GeocodeResult.ok(
            latitude=primeiro["position"]["lat"],
            longitude=primeiro["position"]["lng"],
            precision=precisao,
            normalized_address=(primeiro.get("address") or {}).get("label"),
            provider=self.nome,
            raw=primeiro,
        )
