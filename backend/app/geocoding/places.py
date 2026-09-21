"""Busca de endereco com sugestoes, pelo Google Places (API New).

E o campo do Google Maps: a pessoa digita "Afonso Pena 30", o Google sugere
enderecos que EXISTEM, ela escolhe um, e o ponto vem do cadastro dele.

Existe por causa de uma medicao feita em 21/09/2026, nos mesmos oito
enderecos reais de Campo Grande:

    Nominatim (gratuito) ....... numero certo em 0 de 8
    Google Places .............. numero certo em 8 de 8

O pino do Nominatim ficava de 900 m a 2,3 km do ponto do Google em sete
dos oito. O motivo esta em app/services/precisao.py: o OpenStreetMap tem
numero de porta em cerca de 530 predios da cidade.

Tres decisoes que valem explicacao:

1. A chamada sai do SERVIDOR, nunca do navegador. A chave fica no .env e o
   repositorio e publico; uma chave no JavaScript da pagina e uma chave
   exposta para qualquer um que abra o inspetor.

2. Token de sessao. Sem ele o Google cobra cada tecla digitada como uma
   consulta separada; com ele, a digitacao inteira mais o detalhe do lugar
   escolhido contam como uma sessao. O token e gerado no navegador e viaja
   em cada chamada.

3. "Achou o endereco" nao e o mesmo que "o ponto e o portao". O Places diz
   ONDE fica o lugar, mas nao diz se aquele ponto e o telhado ou uma
   estimativa entre os numeros da quadra. Quem diz e a Geocoding API, pelo
   `location_type`. So ROOFTOP vira EXATO e dispensa conferencia; o resto
   entra como RUA — com o pino ja no lugar certo, o que transforma a
   confirmacao num olhar e um clique.

   Se a Geocoding API nao estiver ativada no projeto do Google, nao ha
   como saber, e o sistema assume o pior: RUA. Errar para "impreciso" custa
   uma confirmacao; errar para "exato" custa uma entrega.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings
from app.core.enums import GeocodePrecision
from app.core.errors import NotFoundError, ServiceUnavailableError

logger = logging.getLogger(__name__)

AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
DETALHE_URL = "https://places.googleapis.com/v1/places/{place_id}"
GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"

#: Centro de Campo Grande. Vies, nao restricao: a operacao e na cidade, mas
#: pode haver servico no interior do estado, e uma restricao dura esconderia
#: esses enderecos em vez de so rebaixa-los na lista.
CAMPO_GRANDE = {"latitude": -20.4697, "longitude": -54.6201}
RAIO_VIES_M = 50_000.0

#: So o que o sistema usa. O Google cobra o detalhe pela faixa dos campos
#: pedidos, entao pedir "tudo" sairia mais caro sem servir para nada.
CAMPOS_DETALHE = "id,formattedAddress,location,types,addressComponents"

_PRECISAO_POR_TIPO_DE_PONTO = {
    "ROOFTOP": GeocodePrecision.EXATO,
    "RANGE_INTERPOLATED": GeocodePrecision.RUA,
    "GEOMETRIC_CENTER": GeocodePrecision.RUA,
    "APPROXIMATE": GeocodePrecision.BAIRRO,
}

#: Depois de uma recusa da Geocoding API (tipicamente: nao ativada no
#: projeto), para de tentar por um tempo. Tentar a cada escolha so somaria
#: latencia a uma resposta que ja se sabe qual e. Nao e para sempre: quem
#: ativar a API no console nao precisa reiniciar o servidor.
PAUSA_APOS_RECUSA_S = 600
_geocoding_recusado_em: float | None = None

#: Conexao mantida com o Google entre chamadas.
#:
#: Nao e otimizacao prematura, foi medido: abrindo um cliente novo por
#: chamada, cada sugestao levava cerca de 2 s — o aperto de mao TLS a cada
#: tecla. Reaproveitando a conexao, 240 a 700 ms. A diferenca entre um campo
#: que parece o Google Maps e um que parece travado.
_cliente: httpx.Client | None = None
_trava_cliente = threading.Lock()


def _http() -> httpx.Client:
    global _cliente
    if _cliente is None:
        with _trava_cliente:
            if _cliente is None:
                _cliente = httpx.Client(timeout=8.0)
    return _cliente


@dataclass(frozen=True)
class Sugestao:
    place_id: str
    texto: str
    principal: str
    secundario: str


@dataclass(frozen=True)
class Lugar:
    place_id: str
    endereco_formatado: str
    latitude: float
    longitude: float
    precision: GeocodePrecision
    #: ROOFTOP, RANGE_INTERPOLATED... ou None quando a Geocoding API nao
    #: respondeu. None e registrado como tal, nunca adivinhado.
    tipo_ponto: str | None
    logradouro: str | None = None
    numero: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    uf: str | None = None
    cep: str | None = None
    tipos: list[str] = field(default_factory=list)


def chave() -> str:
    return get_settings().google_maps_api_key.strip()


def disponivel() -> bool:
    return bool(chave())


def _exigir_chave() -> str:
    valor = chave()
    if not valor:
        raise ServiceUnavailableError(
            "A busca com sugestoes nao esta configurada. "
            "Defina GOOGLE_MAPS_API_KEY no .env do backend."
        )
    return valor


def _erro_do_google(resposta: httpx.Response) -> ServiceUnavailableError:
    """Traduz o erro do Google numa mensagem que diz o que fazer."""
    try:
        erro = resposta.json().get("error", {})
    except ValueError:
        erro = {}
    razoes = {d.get("reason") for d in erro.get("details", []) if d.get("reason")}
    status_google = erro.get("status", "")

    if "API_KEY_INVALID" in razoes:
        mensagem = "O Google recusou a chave de API. Confira GOOGLE_MAPS_API_KEY."
    elif "BILLING_DISABLED" in razoes:
        mensagem = "O projeto do Google esta sem faturamento ativo."
    elif status_google == "RESOURCE_EXHAUSTED" or resposta.status_code == 429:
        mensagem = "A cota diaria do Google acabou."
    elif status_google == "PERMISSION_DENIED":
        mensagem = "A chave nao tem permissao para a Places API (New)."
    else:
        mensagem = f"O Google respondeu {resposta.status_code}."

    logger.warning("Places: %s %s %s", resposta.status_code, status_google, sorted(razoes))
    return ServiceUnavailableError(mensagem, details={"status_google": status_google})


def sugerir(texto: str, sessao: str) -> list[Sugestao]:
    """Sugestoes enquanto a pessoa digita."""
    valor = _exigir_chave()
    corpo = {
        "input": texto,
        "sessionToken": sessao,
        "languageCode": "pt-BR",
        "includedRegionCodes": ["br"],
        "locationBias": {"circle": {"center": CAMPO_GRANDE, "radius": RAIO_VIES_M}},
    }
    try:
        cliente = _http()
        resposta = cliente.post(
            AUTOCOMPLETE_URL,
            json=corpo,
            headers={"X-Goog-Api-Key": valor},
        )
    except httpx.HTTPError as exc:
        logger.warning("Places inacessivel: %s", exc)
        raise ServiceUnavailableError("Nao foi possivel falar com o Google agora.") from exc

    if resposta.status_code != 200:
        raise _erro_do_google(resposta)

    sugestoes = []
    for item in resposta.json().get("suggestions", []):
        previsao = item.get("placePrediction")
        if not previsao:
            continue
        formato = previsao.get("structuredFormat", {})
        sugestoes.append(
            Sugestao(
                place_id=previsao["placeId"],
                texto=previsao.get("text", {}).get("text", ""),
                principal=formato.get("mainText", {}).get("text", ""),
                secundario=formato.get("secondaryText", {}).get("text", ""),
            )
        )
    return sugestoes


def _componente(componentes: list[dict], *tipos: str, curto: bool = False) -> str | None:
    for tipo in tipos:
        for c in componentes:
            if tipo in c.get("types", []):
                return c.get("shortText" if curto else "longText")
    return None


def _tipo_do_ponto(place_id: str, valor: str) -> str | None:
    """Pergunta a Geocoding API se o ponto e o telhado ou uma estimativa.

    Devolve None quando nao da para saber. None nunca vira EXATO.
    """
    global _geocoding_recusado_em
    if (
        _geocoding_recusado_em is not None
        and time.monotonic() - _geocoding_recusado_em < PAUSA_APOS_RECUSA_S
    ):
        return None

    try:
        cliente = _http()
        dados = cliente.get(
            GEOCODING_URL, params={"place_id": place_id, "key": valor}
        ).json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.info("Geocoding API sem resposta para o tipo do ponto: %s", exc)
        return None

    status_google = dados.get("status")
    if status_google == "OK" and dados.get("results"):
        return dados["results"][0].get("geometry", {}).get("location_type")
    if status_google == "REQUEST_DENIED":
        _geocoding_recusado_em = time.monotonic()
        logger.warning(
            "Geocoding API recusada (provavelmente nao ativada no projeto). "
            "Sem ela nenhum ponto do Google vira EXATO; todos pedem confirmacao."
        )
    return None


def detalhar(place_id: str, sessao: str | None) -> Lugar:
    """O lugar escolhido: endereco, componentes e o ponto no mapa.

    Fecha a sessao de digitacao iniciada em `sugerir`.
    """
    valor = _exigir_chave()
    params = {"languageCode": "pt-BR"}
    if sessao:
        params["sessionToken"] = sessao

    try:
        cliente = _http()
        resposta = cliente.get(
            DETALHE_URL.format(place_id=place_id),
            params=params,
            headers={"X-Goog-Api-Key": valor, "X-Goog-FieldMask": CAMPOS_DETALHE},
        )
    except httpx.HTTPError as exc:
        raise ServiceUnavailableError("Nao foi possivel falar com o Google agora.") from exc

    if resposta.status_code == 404:
        raise NotFoundError("O Google nao reconhece mais este lugar. Busque de novo.")
    if resposta.status_code != 200:
        raise _erro_do_google(resposta)

    dados = resposta.json()
    local = dados.get("location") or {}
    if "latitude" not in local:
        raise NotFoundError("O Google devolveu o lugar sem coordenada.")

    componentes = dados.get("addressComponents", [])
    tipos = dados.get("types", [])
    tipo_ponto = _tipo_do_ponto(place_id, valor)

    if tipo_ponto:
        precisao = _PRECISAO_POR_TIPO_DE_PONTO.get(tipo_ponto, GeocodePrecision.RUA)
    elif "locality" in tipos or "administrative_area_level_2" in tipos:
        precisao = GeocodePrecision.CIDADE
    elif "sublocality" in tipos or "neighborhood" in tipos:
        precisao = GeocodePrecision.BAIRRO
    else:
        # Sem o tipo do ponto nao ha como provar que e o portao.
        precisao = GeocodePrecision.RUA

    return Lugar(
        place_id=dados.get("id", place_id),
        endereco_formatado=dados.get("formattedAddress", ""),
        latitude=float(local["latitude"]),
        longitude=float(local["longitude"]),
        precision=precisao,
        tipo_ponto=tipo_ponto,
        logradouro=_componente(componentes, "route"),
        numero=_componente(componentes, "street_number"),
        bairro=_componente(componentes, "sublocality_level_1", "sublocality", "neighborhood"),
        # Em Campo Grande o Google as vezes poe a cidade so no nivel 2.
        cidade=_componente(componentes, "locality", "administrative_area_level_2"),
        uf=_componente(componentes, "administrative_area_level_1", curto=True),
        cep=_componente(componentes, "postal_code"),
        tipos=tipos,
    )
