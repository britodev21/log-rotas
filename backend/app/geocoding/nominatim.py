"""Adaptador do Nominatim (OpenStreetMap)."""

from __future__ import annotations

import logging
import threading
import time

import httpx

from app.core.config import get_settings
from app.core.enums import GeocodePrecision
from app.geocoding.base import Candidato, GeocodeResult

logger = logging.getLogger(__name__)

#: A politica de uso do Nominatim permite no maximo 1 requisicao por
#: segundo. Ultrapassar isso faz o IP ser bloqueado — nao ha aviso, o
#: servico simplesmente para de responder.
INTERVALO_MINIMO_S = 1.05

#: Tipos do OSM traduzidos para o nivel de precisao que interessa ao
#: planejamento. Uma coordenada no nivel de BAIRRO pode deixar a parada a
#: centenas de metros do portao, e a rota calculada em cima dela e otimista.
_PRECISAO_POR_CLASSE = {
    "building": GeocodePrecision.EXATO,
    "house": GeocodePrecision.EXATO,
    "place": GeocodePrecision.EXATO,
    "shop": GeocodePrecision.EXATO,
    "amenity": GeocodePrecision.EXATO,
    "highway": GeocodePrecision.RUA,
    "road": GeocodePrecision.RUA,
    "suburb": GeocodePrecision.BAIRRO,
    "neighbourhood": GeocodePrecision.BAIRRO,
    "city": GeocodePrecision.CIDADE,
    "town": GeocodePrecision.CIDADE,
    "municipality": GeocodePrecision.CIDADE,
    "administrative": GeocodePrecision.CIDADE,
}


class _LimitadorDeTaxa:
    """Garante o intervalo minimo entre requisicoes ao provedor.

    Simples de proposito: um lock de processo. Em varios workers isso deixa
    de valer, e o limite passa a ser assunto de fila externa — registrado em
    docs/LIMITACOES.md, nao escondido aqui.
    """

    def __init__(self, intervalo: float) -> None:
        self._intervalo = intervalo
        self._ultimo = 0.0
        self._lock = threading.Lock()

    def aguardar(self) -> None:
        with self._lock:
            espera = self._intervalo - (time.monotonic() - self._ultimo)
            if espera > 0:
                time.sleep(espera)
            self._ultimo = time.monotonic()


def _precisao(item: dict) -> GeocodePrecision | None:
    for chave in (item.get("class"), item.get("type"), item.get("addresstype")):
        if chave in _PRECISAO_POR_CLASSE:
            return _PRECISAO_POR_CLASSE[chave]
    return None


class NominatimProvider:
    """Geocodificacao pelo Nominatim.

    Gratuito, sem chave e sem cartao — o que o torna a escolha certa para
    comecar. O preco e o limite de uma requisicao por segundo e a proibicao
    de uso pesado, que precisam ser respeitados para o IP nao ser bloqueado.
    """

    nome = "nominatim"

    def __init__(self, *, base_url: str | None = None, user_agent: str | None = None) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.nominatim_base_url).rstrip("/")
        # User-Agent identificando a aplicacao e OBRIGATORIO pela politica
        # do servico; requisicao anonima e recusada.
        self.user_agent = user_agent or settings.nominatim_user_agent
        self._limitador = _LimitadorDeTaxa(INTERVALO_MINIMO_S)

    def geocode(self, endereco: str) -> GeocodeResult:
        if not endereco or not endereco.strip():
            return GeocodeResult.nao_encontrado(provider=self.nome)

        self._limitador.aguardar()

        params = {
            "q": endereco.strip(),
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": 5,
            # Restringe ao Brasil: sem isso "Rua 14 de Julho" casa com
            # endereco em Portugal e o pino cai do outro lado do Atlantico.
            "countrycodes": "br",
        }

        try:
            with httpx.Client(timeout=12.0, headers={"User-Agent": self.user_agent}) as cliente:
                resposta = cliente.get(f"{self.base_url}/search", params=params)
                resposta.raise_for_status()
                itens = resposta.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("Nominatim respondeu %s", exc.response.status_code)
            return GeocodeResult.erro(
                f"O servico de geocodificacao respondeu {exc.response.status_code}.",
                provider=self.nome,
            )
        except httpx.HTTPError as exc:
            logger.warning("Falha de rede ao consultar o Nominatim: %s", exc)
            return GeocodeResult.erro(
                "Nao foi possivel consultar o servico de geocodificacao.",
                provider=self.nome,
            )
        except ValueError:
            return GeocodeResult.erro(
                "Resposta invalida do servico de geocodificacao.", provider=self.nome
            )

        if not itens:
            return GeocodeResult.nao_encontrado(provider=self.nome)

        candidatos = [
            Candidato(
                latitude=float(i["lat"]),
                longitude=float(i["lon"]),
                display_name=i.get("display_name", ""),
                precision=_precisao(i),
            )
            for i in itens
        ]

        primeiro = itens[0]
        precisao = _precisao(primeiro)

        # Varias respostas de precisao grosseira significam que o provedor
        # nao sabe qual e — devolver a primeira seria escolher no escuro.
        # Com precisao EXATO ou RUA, a primeira e confiavel o bastante.
        if len(candidatos) > 1 and precisao in (
            GeocodePrecision.BAIRRO,
            GeocodePrecision.CIDADE,
            None,
        ):
            return GeocodeResult.ambiguo(candidatos, provider=self.nome)

        return GeocodeResult.ok(
            latitude=float(primeiro["lat"]),
            longitude=float(primeiro["lon"]),
            precision=precisao,
            normalized_address=primeiro.get("display_name"),
            provider=self.nome,
            raw=primeiro,
        )
