"""Adaptador da Geocoding API do Google.

Existe por uma razao medida. Em Campo Grande o OpenStreetMap tem numero de
porta em cerca de 530 predios, e o Nominatim resolveu o numero em ZERO de
oito enderecos reais das avenidas principais (ver app/services/precisao.py).
Isso obriga a confirmar o ponto a mao em praticamente todo endereco novo.

O Google mantem base propria de enderecos e resolve no numero na maior
parte do Brasil urbano. Com ele a confirmacao manual deixa de ser a regra e
volta a ser a excecao, que e o que este adaptador compra.

Custa dinheiro e exige cartao. A decisao e do dono da operacao; o codigo so
precisa estar pronto para quando ela for tomada — basta

    GEOCODING_PROVIDER=google
    GEOCODING_PROVIDER_KEY=<a chave>

no .env. Nenhuma outra linha do sistema muda.

AVISO DE HONESTIDADE: este arquivo foi escrito e testado contra respostas
gravadas, nao contra a API real — nao ha chave disponivel aqui. A leitura
das respostas esta coberta por testes; o que NAO foi exercitado e a
conversa de rede com o Google (formato de erro real, cota estourada,
chave restrita por IP ou referrer). Na primeira vez que uma chave for
configurada, confira na tela um endereco conhecido antes de confiar.
"""

from __future__ import annotations

import logging

import httpx

from app.core.config import get_settings
from app.core.enums import GeocodePrecision
from app.geocoding.base import Candidato, GeocodeResult

logger = logging.getLogger(__name__)

URL = "https://maps.googleapis.com/maps/api/geocode/json"

#: Como o Google descreve a origem da coordenada, traduzido para o que o
#: planejamento precisa saber.
#:
#: ROOFTOP             o ponto e o endereco. Entra em rota sem conferencia.
#: RANGE_INTERPOLATED  o Google sabe os numeros das pontas da quadra e
#:                     INTERPOLOU o resto. Costuma cair perto, e perto nao
#:                     e o portao: fica como RUA e pede confirmacao. Melhor
#:                     uma conferencia a mais que uma entrega na casa
#:                     errada.
#: GEOMETRIC_CENTER    centro da via ou do poligono.
#: APPROXIMATE         regiao.
_PRECISAO = {
    "ROOFTOP": GeocodePrecision.EXATO,
    "RANGE_INTERPOLATED": GeocodePrecision.RUA,
    "GEOMETRIC_CENTER": GeocodePrecision.RUA,
    "APPROXIMATE": GeocodePrecision.BAIRRO,
}

#: Status que a API devolve dentro de um HTTP 200. Tratar so o codigo HTTP
#: aceitaria uma resposta de cota estourada como se fosse endereco nao
#: encontrado, e o endereco iria para a fila como "corrija o endereco"
#: quando o problema era a fatura.
_SEM_RESULTADO = {"ZERO_RESULTS"}
_FALHA_DO_SERVICO = {
    "OVER_QUERY_LIMIT": "A cota da Geocoding API do Google acabou.",
    "REQUEST_DENIED": "O Google recusou a requisicao. Confira a chave de API.",
    "INVALID_REQUEST": "Requisicao invalida para a Geocoding API.",
    "UNKNOWN_ERROR": "O Google respondeu com erro temporario.",
}


class GoogleProvider:
    """Geocodificacao pela Geocoding API do Google."""

    nome = "google"

    def __init__(self, *, chave: str | None = None) -> None:
        settings = get_settings()
        # Uma chave do Google serve para tudo; a especifica tem prioridade.
        self.chave = (
            chave or settings.geocoding_provider_key or settings.google_maps_api_key
        )
        if not self.chave:
            raise ValueError(
                "GEOCODING_PROVIDER=google exige GEOCODING_PROVIDER_KEY "
                "ou GOOGLE_MAPS_API_KEY no .env."
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
            "address": endereco.strip(),
            "key": self.chave,
            # Restringe ao Brasil: sem isso "Rua 14 de Julho" casa com
            # endereco em Portugal e o pino cai do outro lado do Atlantico.
            "components": "country:BR",
            "region": "br",
            "language": "pt-BR",
        }

        try:
            with httpx.Client(timeout=12.0) as cliente:
                resposta = cliente.get(URL, params=params)
                resposta.raise_for_status()
                dados = resposta.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("Google respondeu %s", exc.response.status_code)
            return GeocodeResult.erro(
                f"O servico de geocodificacao respondeu {exc.response.status_code}.",
                provider=self.nome,
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

        status = dados.get("status", "")
        if status in _FALHA_DO_SERVICO:
            logger.warning("Google: %s", status)
            return GeocodeResult.erro(_FALHA_DO_SERVICO[status], provider=self.nome)
        if status in _SEM_RESULTADO or not dados.get("results"):
            return GeocodeResult.nao_encontrado(provider=self.nome)

        itens = dados["results"]
        candidatos = [
            Candidato(
                latitude=i["geometry"]["location"]["lat"],
                longitude=i["geometry"]["location"]["lng"],
                display_name=i.get("formatted_address", ""),
                precision=_PRECISAO.get(i["geometry"].get("location_type")),
            )
            for i in itens
        ]

        primeiro = itens[0]
        precisao = _PRECISAO.get(primeiro["geometry"].get("location_type"))

        # `partial_match` e o Google dizendo que nao casou o endereco
        # inteiro — tipicamente porque o numero nao existe naquela via.
        # Gravar como certo seria transformar a duvida DELE em certeza
        # NOSSA.
        if primeiro.get("partial_match"):
            return GeocodeResult.ambiguo(candidatos, provider=self.nome)

        if len(candidatos) > 1 and precisao is not GeocodePrecision.EXATO:
            return GeocodeResult.ambiguo(candidatos, provider=self.nome)

        return GeocodeResult.ok(
            latitude=primeiro["geometry"]["location"]["lat"],
            longitude=primeiro["geometry"]["location"]["lng"],
            precision=precisao,
            normalized_address=primeiro.get("formatted_address"),
            provider=self.nome,
            raw=primeiro,
        )
