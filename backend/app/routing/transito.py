"""Trânsito: quanto o tempo de agora difere do tempo de via livre.

O OSRM calcula o tempo com as velocidades do mapa, com a rua vazia. Não
existe fonte gratuita de trânsito em tempo real — quem tem o dado é quem
tem os celulares na rua (Google, HERE, TomTom). Este adaptador usa a Routes
API do Google, com a mesma chave da busca de endereço.

Decisão de custo, que molda tudo aqui: a previsão de chegada é recalculada
a cada ~45 s por rota. Chamar o Google nesse ritmo daria centenas de
chamadas pagas por caminhão por dia. Em vez disso, o Google é consultado no
máximo a cada `traffic_refresh_s` (5 min por padrão) e devolve um FATOR —
"agora está 30% mais lento que o OSRM prevê". Nos intervalos, o fator é
aplicado sobre o tempo do OSRM, que é grátis.

O fator compara o tempo com trânsito do Google com o do OSRM para os
MESMOS pontos, então também corrige o otimismo do OSRM, que costuma prever
menos tempo do que um caminhão de fato leva na cidade.

O planejamento usa a mesma chamada, com a hora de partida no futuro — ver
app/routing/matriz_transito.py. Conferido contra a API real em 22/09/2026:
com partida futura o Google devolve o trânsito PREVISTO para aquela hora, e
a chamada funciona sem faturamento ativo no projeto (a computeRouteMatrix,
não: responde 403 pedindo faturamento).
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
CAMPOS = "routes.legs.duration,routes.legs.staticDuration,routes.legs.distanceMeters"

#: A Routes API aceita até 25 pontos intermediários.
MAXIMO_INTERMEDIARIOS = 25

#: Limites do fator. Fora disso é mais provável erro de dado do que
#: trânsito: um fator 10 faria a previsão dizer "chega amanhã".
FATOR_MINIMO = 0.6
FATOR_MAXIMO = 3.0


class TransitoIndisponivel(RuntimeError):
    pass


@dataclass(frozen=True)
class TempoComTransito:
    duracoes_s: list[int]
    duracoes_livres_s: list[int]
    distancias_m: list[int] = field(default_factory=list)

    @property
    def total_s(self) -> int:
        return sum(self.duracoes_s)


_cliente: httpx.Client | None = None
_trava = threading.Lock()


def _http() -> httpx.Client:
    global _cliente
    if _cliente is None:
        with _trava:
            if _cliente is None:
                _cliente = httpx.Client(timeout=10.0)
    return _cliente


def disponivel() -> bool:
    settings = get_settings()
    return settings.traffic_provider.lower() == "google" and bool(
        settings.google_maps_api_key.strip()
    )


def _segundos(texto: str | None) -> int:
    """A Routes API devolve duração como texto: "754s"."""
    if not texto:
        return 0
    return round(float(texto.rstrip("s")))


def _ponto(lat: float, lon: float) -> dict:
    return {"location": {"latLng": {"latitude": lat, "longitude": lon}}}


def _causa(resposta: httpx.Response) -> str:
    try:
        corpo = resposta.json()
    except ValueError:
        return f"o Google respondeu {resposta.status_code}"
    # Alguns métodos da Routes API devolvem o erro dentro de uma lista.
    if isinstance(corpo, list):
        corpo = corpo[0] if corpo and isinstance(corpo[0], dict) else {}
    erro = corpo.get("error", {}) if isinstance(corpo, dict) else {}
    razoes = {d.get("reason") for d in erro.get("details", []) if d.get("reason")}
    mensagem = (erro.get("message") or "").lower()
    if "BILLING_DISABLED" in razoes or "billing" in mensagem:
        return "o projeto do Google está sem faturamento ativo"
    if "SERVICE_DISABLED" in razoes:
        return "a Routes API não está ativada no projeto"
    if "API_KEY_SERVICE_BLOCKED" in razoes or "not authorized" in mensagem:
        return "a chave não tem a Routes API nas restrições de API"
    if "API_KEY_INVALID" in razoes:
        return "a chave foi recusada"
    if resposta.status_code == 429:
        return "a cota do Google acabou"
    return f"o Google respondeu {resposta.status_code}"


def _instante(partida: datetime) -> str:
    return partida.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def consultar(
    pontos: list[tuple[float, float]], partida: datetime | None = None
) -> TempoComTransito:
    """Tempo com trânsito, por perna, passando pelos pontos em ordem.

    `partida` no futuro: trânsito previsto para aquela hora. Nula ou no
    passado: trânsito de agora — a API recusa partida no passado.
    """
    if not disponivel():
        raise TransitoIndisponivel("trânsito não configurado")
    if len(pontos) < 2:
        return TempoComTransito([], [])

    # Mais pontos do que a API aceita: usa os primeiros. O trânsito que
    # importa para a previsão é o das próximas paradas, não o do fim do dia.
    pontos = pontos[: MAXIMO_INTERMEDIARIOS + 2]
    corpo = {
        "origin": _ponto(*pontos[0]),
        "destination": _ponto(*pontos[-1]),
        "intermediates": [_ponto(*p) for p in pontos[1:-1]],
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
        "languageCode": "pt-BR",
    }
    if partida is not None and partida > datetime.now(UTC) + timedelta(minutes=1):
        corpo["departureTime"] = _instante(partida)
    try:
        resposta = _http().post(
            URL,
            json=corpo,
            headers={
                "X-Goog-Api-Key": get_settings().google_maps_api_key.strip(),
                "X-Goog-FieldMask": CAMPOS,
            },
        )
    except httpx.HTTPError as exc:
        raise TransitoIndisponivel(f"Google inacessível: {exc}") from exc

    if resposta.status_code != 200:
        causa = _causa(resposta)
        logger.warning("Routes API recusada: %s", causa)
        raise TransitoIndisponivel(causa)

    rotas = resposta.json().get("routes") or []
    if not rotas:
        raise TransitoIndisponivel("o Google não encontrou rota entre os pontos")

    pernas = rotas[0].get("legs", [])
    return TempoComTransito(
        duracoes_s=[_segundos(p.get("duration")) for p in pernas],
        duracoes_livres_s=[_segundos(p.get("staticDuration")) for p in pernas],
        distancias_m=[int(p.get("distanceMeters") or 0) for p in pernas],
    )


def fator(com_transito_s: int, osrm_s: int) -> float:
    """Quanto multiplicar o tempo do OSRM para chegar no do Google."""
    if osrm_s <= 0 or com_transito_s <= 0:
        return 1.0
    return max(FATOR_MINIMO, min(FATOR_MAXIMO, com_transito_s / osrm_s))
