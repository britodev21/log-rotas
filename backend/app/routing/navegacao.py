"""Navegacao: rota com manobras, em portugues, e o ponto de chegada certo.

Existe porque o motorista navegava pelo Google Maps, e isso tinha um custo
escondido: com o Google Maps na frente, a pagina do Log Rotas vai para
segundo plano e o navegador PARA o GPS dela. Navegando por aqui, o app fica
aberto e o rastreamento funciona o tempo todo — sem precisar de aplicativo
nativo.

Duas coisas nao obvias acontecem aqui:

1. O PONTO DE CHEGADA nao e o pino da entrega. O pino fica no lote (o
   Google aponta o telhado), e o OSRM encosta o destino na rua mais proxima
   DO PONTO — que pode ser a rua de tras. Medido em Campo Grande: para "Rua
   Bahia, 500" a rota terminava na Rua Piratininga, dando a volta no
   quarteirao. Escolhendo, entre as ruas proximas, a do proprio endereco, a
   chegada passou a ser pela Rua Bahia e a rota ficou 475 m mais curta.

2. As manobras chegam do OSRM em ingles e em codigo ("turn", "slight
   left"). A traducao para frase e feita aqui, no servidor, para a tela e a
   voz dizerem a mesma coisa.

O servidor do OSRM e o publico de demonstracao (ver docs/SERVICOS_EXTERNOS.md).
Quando ele cai, a rota vira estimativa em linha reta, sem manobras — e a
resposta diz isso.
"""

from __future__ import annotations

import logging
import re
import threading
import unicodedata
from dataclasses import dataclass, field

import httpx

from app.core.config import get_settings
from app.core.enums import MatrixSource
from app.routing.base import Ponto
from app.routing.haversine import HaversineProvider

logger = logging.getLogger(__name__)

#: Quantas ruas proximas considerar ao procurar a do endereco. Cinco cobre
#: esquina e lote de fundo sem pegar rua de outro quarteirao.
RUAS_CANDIDATAS = 5

#: Acima disto a rua "certa" ja esta longe demais do pino para ser a entrada
#: do lote: provavelmente e outro trecho com o mesmo nome.
DISTANCIA_MAXIMA_RUA_M = 80.0


class NavegacaoIndisponivel(RuntimeError):
    pass


@dataclass(frozen=True)
class Manobra:
    tipo: str
    modificador: str | None
    instrucao: str
    rua: str
    #: Comprimento do trecho que COMECA nesta manobra.
    distancia_m: int
    duracao_s: int
    latitude: float
    longitude: float
    saida: int | None = None


@dataclass
class Perna:
    distancia_m: int
    duracao_s: int
    manobras: list[Manobra] = field(default_factory=list)


@dataclass
class RotaNavegavel:
    pernas: list[Perna]
    geometria: str | None
    distancia_m: int
    duracao_s: int
    source: MatrixSource
    #: Verdadeiro quando os numeros sao linha reta, nao estrada.
    estimada: bool
    aviso: str | None = None


# --------------------------------------------------------------------------- #
# Conexao
# --------------------------------------------------------------------------- #
_cliente: httpx.Client | None = None
_trava = threading.Lock()


def _http() -> httpx.Client:
    """Conexao mantida com o OSRM. Numa navegacao a rota e recalculada a
    cada desvio; abrir conexao nova a cada vez somaria segundos a cada
    recalculo (medido no Google: ~2 s contra 250-700 ms)."""
    global _cliente
    if _cliente is None:
        with _trava:
            if _cliente is None:
                _cliente = httpx.Client(timeout=15.0)
    return _cliente


def _base() -> str:
    return get_settings().osrm_base_url.rstrip("/")


def _osrm_ligado() -> bool:
    """Respeita a mesma escolha do planejamento. Configurado sem OSRM, a
    navegacao tambem nao o chama: linha reta, e a resposta diz isso."""
    return get_settings().matrix_provider.lower() == "osrm"


def _get(caminho: str, params: dict) -> dict:
    try:
        resposta = _http().get(f"{_base()}{caminho}", params=params)
        resposta.raise_for_status()
        dados = resposta.json()
    except httpx.HTTPError as exc:
        raise NavegacaoIndisponivel(f"Servico de rotas inacessivel: {exc}") from exc
    except ValueError as exc:
        raise NavegacaoIndisponivel("Resposta invalida do servico de rotas.") from exc
    if dados.get("code") != "Ok":
        raise NavegacaoIndisponivel(dados.get("message") or dados.get("code") or "erro")
    return dados


# --------------------------------------------------------------------------- #
# Ponto de chegada
# --------------------------------------------------------------------------- #
_PREFIXOS = (
    "rua ", "r ", "avenida ", "av ", "travessa ", "tv ", "alameda ", "al ",
    "estrada ", "rodovia ", "praca ", "largo ", "viaduto ", "anel viario ",
)


def _normalizar_rua(texto: str | None) -> str:
    t = unicodedata.normalize("NFKD", texto or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = " ".join(re.sub(r"[^\w\s]", " ", t).split())
    for prefixo in _PREFIXOS:
        if t.startswith(prefixo):
            return t[len(prefixo):]
    return t


def rua_do_endereco(endereco: str | None) -> str | None:
    """"Rua Bahia, 500, Itanhanga Park, ..." -> "Rua Bahia"."""
    if not endereco:
        return None
    primeiro = endereco.split(",")[0].strip()
    return primeiro or None


_cache_chegada: dict[tuple[float, float, str], tuple[float, float]] = {}
_LIMITE_CACHE = 5000


def ponto_de_chegada(
    latitude: float, longitude: float, endereco: str | None
) -> tuple[float, float]:
    """Onde o caminhao deve parar para esta entrega.

    Entre as ruas mais proximas do pino, prefere a que tem o nome do
    endereco. Sem nome que bata — ou sem servico de rotas — devolve o proprio
    pino, que e o comportamento anterior: pior, mas nunca inventado.
    """
    if not _osrm_ligado():
        return (latitude, longitude)

    rua = rua_do_endereco(endereco)
    alvo = _normalizar_rua(rua)
    chave = (round(latitude, 6), round(longitude, 6), alvo)
    if chave in _cache_chegada:
        return _cache_chegada[chave]

    ponto = (latitude, longitude)
    if alvo:
        try:
            dados = _get(
                f"/nearest/v1/driving/{longitude},{latitude}",
                {"number": RUAS_CANDIDATAS},
            )
            for w in dados.get("waypoints", []):
                if (
                    _normalizar_rua(w.get("name")) == alvo
                    and float(w.get("distance", 1e9)) <= DISTANCIA_MAXIMA_RUA_M
                ):
                    lon, lat = w["location"]
                    ponto = (float(lat), float(lon))
                    break
        except NavegacaoIndisponivel as exc:
            logger.info("Sem ponto de chegada pela rua do endereco: %s", exc)
            return ponto  # nao guarda: tenta de novo quando o servico voltar

    if len(_cache_chegada) < _LIMITE_CACHE:
        _cache_chegada[chave] = ponto
    return ponto


# --------------------------------------------------------------------------- #
# Instrucoes em portugues
# --------------------------------------------------------------------------- #
_DIRECAO = {
    "right": "à direita",
    "left": "à esquerda",
    "slight right": "levemente à direita",
    "slight left": "levemente à esquerda",
    "sharp right": "acentuadamente à direita",
    "sharp left": "acentuadamente à esquerda",
    "straight": "em frente",
    "uturn": "o retorno",
}

#: Tipos de via masculinos pedem "no"; o resto (rua, avenida, travessa,
#: alameda, estrada, rodovia, praca) pede "na".
_MASCULINOS = ("viaduto", "anel", "largo", "contorno", "acesso", "elevado", "beco", "trevo")


def _na(rua: str) -> str:
    if not rua:
        return ""
    primeira = _normalizar_rua_sem_prefixo(rua).split(" ")[0]
    return f"no {rua}" if primeira in _MASCULINOS else f"na {rua}"


def _normalizar_rua_sem_prefixo(rua: str) -> str:
    t = unicodedata.normalize("NFKD", rua)
    return "".join(c for c in t if not unicodedata.combining(c)).lower()


def _ordinal(n: int | None) -> str:
    return f"{n}ª" if n else "próxima"


def instrucao(tipo: str, modificador: str | None, rua: str, saida: int | None = None) -> str:
    """Frase da manobra, como a tela mostra e a voz fala."""
    rua = (rua or "").strip()
    na_rua = _na(rua)
    if not rua:
        pela = ""
    elif na_rua.startswith("no "):
        pela = f"pelo {rua}"
    else:
        pela = f"pela {rua}"
    direcao = _DIRECAO.get(modificador or "", "")

    if tipo == "depart":
        return f"Siga {pela}".strip() if rua else "Siga em frente"
    if tipo == "arrive":
        if modificador in ("left", "slight left", "sharp left"):
            return "Destino à esquerda"
        if modificador in ("right", "slight right", "sharp right"):
            return "Destino à direita"
        return "Você chegou ao destino"
    if tipo in ("roundabout", "rotary"):
        destino = f" para {'a' if not na_rua.startswith('no ') else 'o'} {rua}" if rua else ""
        return f"Na rotatória, pegue a {_ordinal(saida)} saída{destino}"
    if tipo in ("exit roundabout", "exit rotary"):
        return f"Saia da rotatória {pela}".strip()
    if tipo == "roundabout turn":
        return f"Na rotatória, vire {direcao} {na_rua}".strip()
    if modificador == "uturn":
        return f"Faça o retorno {na_rua}".strip()
    if tipo == "turn":
        if modificador == "straight":
            return f"Siga em frente {na_rua}".strip()
        return f"Vire {direcao} {na_rua}".strip()
    if tipo == "end of road":
        return f"No fim da via, vire {direcao} {na_rua}".strip()
    if tipo == "fork":
        lado = direcao.replace("levemente ", "") or "na pista principal"
        return f"Na bifurcação, mantenha-se {lado} {pela}".strip()
    if tipo == "merge":
        return f"Entre {na_rua}".strip() if rua else "Entre na via"
    if tipo == "on ramp":
        return f"Pegue o acesso {pela}".strip()
    if tipo == "off ramp":
        return f"Pegue a saída {pela}".strip()
    # "new name", "continue", "notification", "use lane"
    return f"Continue {pela}".strip() if rua else "Continue em frente"


# --------------------------------------------------------------------------- #
# Rota
# --------------------------------------------------------------------------- #
def _manobras(passos: list[dict]) -> list[Manobra]:
    lista = []
    for s in passos:
        m = s.get("maneuver", {})
        tipo = m.get("type", "")
        mod = m.get("modifier")
        rua = s.get("name") or s.get("ref") or ""
        lon, lat = m.get("location", [0.0, 0.0])
        lista.append(
            Manobra(
                tipo=tipo,
                modificador=mod,
                instrucao=instrucao(tipo, mod, rua, m.get("exit")),
                rua=rua,
                distancia_m=round(s.get("distance", 0)),
                duracao_s=round(s.get("duration", 0)),
                latitude=float(lat),
                longitude=float(lon),
                saida=m.get("exit"),
            )
        )
    return lista


def rota(pontos: list[tuple[float, float]], *, manobras: bool = False) -> RotaNavegavel:
    """Rota passando pelos pontos, na ordem, com uma perna por trecho.

    `manobras=True` pede o passo a passo — so a navegacao precisa, e a
    resposta fica bem maior.
    """
    if len(pontos) < 2:
        return RotaNavegavel([], None, 0, 0, MatrixSource.OSRM, False)

    if not _osrm_ligado():
        return _em_linha_reta(pontos, "servico de rotas desligado na configuracao")

    coords = ";".join(f"{lon},{lat}" for lat, lon in pontos)
    try:
        dados = _get(
            f"/route/v1/driving/{coords}",
            {
                "steps": "true" if manobras else "false",
                "overview": "full",
                "geometries": "polyline",
            },
        )
        melhor = dados["routes"][0]
        pernas = [
            Perna(
                distancia_m=round(p.get("distance", 0)),
                duracao_s=round(p.get("duration", 0)),
                manobras=_manobras(p.get("steps", [])) if manobras else [],
            )
            for p in melhor.get("legs", [])
        ]
        return RotaNavegavel(
            pernas=pernas,
            geometria=melhor.get("geometry"),
            distancia_m=round(melhor.get("distance", 0)),
            duracao_s=round(melhor.get("duration", 0)),
            source=MatrixSource.OSRM,
            estimada=False,
        )
    except (NavegacaoIndisponivel, KeyError, IndexError) as exc:
        logger.warning("Rota de navegacao indisponivel, usando linha reta: %s", exc)
        return _em_linha_reta(pontos, str(exc))


def _em_linha_reta(pontos: list[tuple[float, float]], motivo: str) -> RotaNavegavel:
    estimador = HaversineProvider()
    marcados = [
        Ponto(id=str(i), latitude=lat, longitude=lon) for i, (lat, lon) in enumerate(pontos)
    ]
    matriz = estimador.matriz(marcados)
    pernas = [
        Perna(distancia_m=matriz.distancias[i][i + 1], duracao_s=matriz.duracoes[i][i + 1])
        for i in range(len(pontos) - 1)
    ]
    return RotaNavegavel(
        pernas=pernas,
        geometria=None,
        distancia_m=sum(p.distancia_m for p in pernas),
        duracao_s=sum(p.duracao_s for p in pernas),
        source=MatrixSource.HAVERSINE,
        estimada=True,
        aviso=(
            "O servico de rotas nao respondeu. Distancias e tempos sao estimativa em "
            f"linha reta e nao ha instrucoes de manobra. Motivo: {motivo}"
        ),
    )
