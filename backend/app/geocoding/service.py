"""Orquestracao da geocodificacao: cache, provedor e persistencia."""

from __future__ import annotations

import hashlib
import logging
import re
import unicodedata
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import GeocodePrecision, GeocodeStatus
from app.core.errors import NotFoundError, ValidationError
from app.geocoding.base import GeocodeResult, GeocodingProvider
from app.geocoding.google import GoogleProvider
from app.geocoding.here import HereProvider
from app.geocoding.nominatim import NominatimProvider
from app.models.base_location import BaseLocation
from app.models.customer import Customer
from app.models.delivery import Delivery
from app.models.geocode_cache import GeocodeCache

logger = logging.getLogger(__name__)

#: Entidades que tem endereco e podem ser geocodificadas.
ALVOS = {"entrega": Delivery, "cliente": Customer, "base": BaseLocation}


def normalizar_endereco(endereco: str) -> str:
    """Forma canonica usada como chave do cache.

    Sem acento, sem pontuacao, minusculas, espaco unico. "Av. Afonso Pena,
    1500" e "avenida afonso pena 1500" nao sao a mesma string, mas sao o
    mesmo lugar — e cada consulta desperdicada custa um segundo do unico
    recurso realmente escasso aqui.
    """
    texto = unicodedata.normalize("NFKD", endereco)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^\w\s]", " ", texto.lower())
    return " ".join(texto.split())


def chave_cache(endereco: str) -> str:
    return hashlib.sha256(normalizar_endereco(endereco).encode("utf-8")).hexdigest()


#: Adaptadores disponiveis.
#:
#: `nominatim` e gratuito e nao acha o numero da porta em Campo Grande --
#: cerca de 530 predios da cidade tem numero no OpenStreetMap, e o efeito
#: pratico e que quase todo endereco novo precisa de conferencia manual
#: (ver app/services/precisao.py).
#:
#: `google` e `here` mantem base propria e resolvem no numero. Custam, e
#: e por isso que a troca e uma variavel de ambiente e nao uma decisao
#: tomada dentro do codigo.
PROVEDORES = {
    "nominatim": NominatimProvider,
    "google": GoogleProvider,
    "here": HereProvider,
}


def construir_provider() -> GeocodingProvider:
    """Escolhe o adaptador conforme a configuracao."""
    nome = get_settings().geocoding_provider.lower()
    classe = PROVEDORES.get(nome)
    if classe is None:
        raise ValidationError(
            f"Provedor de geocodificacao desconhecido: {nome}.",
            details={"disponiveis": sorted(PROVEDORES)},
        )
    try:
        return classe()
    except ValueError as exc:
        # Chave faltando. A mensagem precisa dizer o que fazer: um
        # ValueError cru aqui viraria 500 sem explicacao no dia da troca.
        raise ValidationError(str(exc)) from exc


class GeocodingService:
    def __init__(self, session: Session, provider: GeocodingProvider | None = None) -> None:
        self.session = session
        self.provider = provider or construir_provider()

    # ------------------------------------------------------------------ #
    # Consulta
    # ------------------------------------------------------------------ #
    def geocodificar(self, endereco: str, *, usar_cache: bool = True) -> GeocodeResult:
        """Cache -> provedor -> grava no cache."""
        if not endereco or not endereco.strip():
            return GeocodeResult.nao_encontrado(provider=self.provider.nome)

        chave = chave_cache(endereco)

        if usar_cache:
            guardado = self.session.get(GeocodeCache, chave)
            if guardado is not None:
                guardado.hit_count += 1
                return self._do_cache(guardado)

        resultado = self.provider.geocode(endereco)

        # Erro de provedor NAO entra no cache: e falha temporaria de rede ou
        # limite, e guardar transformaria um problema de minutos num
        # endereco permanentemente quebrado.
        if resultado.status != "ERRO_PROVEDOR":
            self._guardar(chave, endereco, resultado)

        return resultado

    def _do_cache(self, registro: GeocodeCache) -> GeocodeResult:
        if registro.status != GeocodeStatus.OK.value:
            return GeocodeResult(
                status=registro.status,
                provider=registro.provider,
                error="Resultado guardado em cache.",
            )
        return GeocodeResult.ok(
            latitude=float(registro.latitude),
            longitude=float(registro.longitude),
            precision=GeocodePrecision(registro.precision) if registro.precision else None,
            normalized_address=registro.display_name,
            provider=registro.provider,
            raw=registro.raw,
        )

    def _guardar(self, chave: str, endereco: str, resultado: GeocodeResult) -> None:
        registro = self.session.get(GeocodeCache, chave) or GeocodeCache(address_hash=chave)
        registro.normalized_address = normalizar_endereco(endereco)[:255]
        registro.provider = resultado.provider
        registro.status = resultado.status
        registro.latitude = resultado.latitude
        registro.longitude = resultado.longitude
        registro.precision = resultado.precision.value if resultado.precision else None
        registro.display_name = (resultado.normalized_address or "")[:400] or None
        registro.raw = resultado.raw
        self.session.add(registro)

    # ------------------------------------------------------------------ #
    # Aplicacao em registros
    # ------------------------------------------------------------------ #
    def aplicar(self, registro, *, forcar: bool = False) -> GeocodeResult:
        """Geocodifica um registro e grava o resultado nele.

        Pino posto a mao (MANUAL) nunca e sobrescrito sem `forcar`. Essa e a
        regra que faz a correcao manual valer alguma coisa: sem ela, a
        proxima rodada automatica desfaria o trabalho do administrador.
        """
        if registro.geocode_status == GeocodeStatus.MANUAL.value and not forcar:
            return GeocodeResult(
                status=GeocodeStatus.MANUAL.value,
                latitude=float(registro.latitude) if registro.latitude else None,
                longitude=float(registro.longitude) if registro.longitude else None,
                provider="manual",
            )

        if not registro.address:
            registro.geocode_status = GeocodeStatus.PENDENTE.value
            registro.geocode_error = "Sem endereco informado."
            return GeocodeResult.nao_encontrado(provider=self.provider.nome)

        resultado = self.geocodificar(registro.address)

        if resultado.sucesso:
            registro.latitude = resultado.latitude
            registro.longitude = resultado.longitude
            registro.geocode_status = GeocodeStatus.OK.value
            registro.geocode_precision = (
                resultado.precision.value if resultado.precision else None
            )
            registro.geocode_provider = resultado.provider
            registro.geocode_error = None
            registro.geocoded_at = datetime.now(UTC)
        elif resultado.status == GeocodeStatus.AMBIGUO.value:
            # Coordenada NAO e gravada: escolher por conta propria entre
            # candidatos e o caminho mais curto para entregar no lugar
            # errado. Fica para o humano decidir na fila de revisao.
            registro.geocode_status = GeocodeStatus.AMBIGUO.value
            registro.geocode_provider = resultado.provider
            registro.geocode_error = resultado.error
        else:
            registro.geocode_status = GeocodeStatus.FALHOU.value
            registro.geocode_provider = resultado.provider
            registro.geocode_error = (resultado.error or "Falha desconhecida.")[:255]

        return resultado

    def geocodificar_lote(self, registros: list, *, forcar: bool = False) -> dict:
        """Processa varios registros, contando os desfechos.

        Um endereco que falha nao interrompe os demais: numa importacao de
        cinquenta, parar no primeiro erro obrigaria a recomecar tudo.
        """
        contagem = {"ok": 0, "ambiguo": 0, "falhou": 0, "manual": 0, "erro_provedor": 0}

        for registro in registros:
            resultado = self.aplicar(registro, forcar=forcar)
            if resultado.sucesso:
                contagem["ok"] += 1
            elif resultado.status == GeocodeStatus.AMBIGUO.value:
                contagem["ambiguo"] += 1
            elif resultado.status == GeocodeStatus.MANUAL.value:
                contagem["manual"] += 1
            elif resultado.status == "ERRO_PROVEDOR":
                contagem["erro_provedor"] += 1
            else:
                contagem["falhou"] += 1

        self.session.commit()
        logger.info("Geocodificacao em lote: %s", contagem)
        return contagem

    # ------------------------------------------------------------------ #
    # Correcao manual
    # ------------------------------------------------------------------ #
    def definir_coordenada(
        self, tipo: str, registro_id: int, latitude: float, longitude: float
    ):
        """Grava o pino ajustado a mao pelo administrador.

        Vira MANUAL, que a geocodificacao automatica nao sobrescreve. E o
        que permite corrigir um endereco uma vez e para sempre — importante
        em Campo Grande, onde loteamento novo e chacara tem cobertura
        irregular no OpenStreetMap.
        """
        registro = self._buscar(tipo, registro_id)
        registro.latitude = latitude
        registro.longitude = longitude
        registro.geocode_status = GeocodeStatus.MANUAL.value
        registro.geocode_precision = GeocodePrecision.EXATO.value
        registro.geocode_provider = "manual"
        registro.geocode_error = None
        registro.geocoded_at = datetime.now(UTC)
        self.session.commit()
        return registro

    def _buscar(self, tipo: str, registro_id: int):
        modelo = ALVOS.get(tipo)
        if modelo is None:
            raise ValidationError(
                f"Tipo desconhecido: {tipo}.", details={"disponiveis": sorted(ALVOS)}
            )
        registro = self.session.get(modelo, registro_id)
        if registro is None:
            raise NotFoundError(f"{tipo.capitalize()} nao encontrado.")
        return registro

    def buscar(self, tipo: str, registro_id: int):
        """Localiza um registro geocodificavel por tipo e id."""
        return self._buscar(tipo, registro_id)

    def geocodificar_um(
        self, tipo: str, registro_id: int, *, forcar: bool = False
    ) -> tuple[object, GeocodeResult]:
        registro = self._buscar(tipo, registro_id)
        resultado = self.aplicar(registro, forcar=forcar)
        self.session.commit()
        return registro, resultado
