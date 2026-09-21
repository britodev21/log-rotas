"""Adaptadores de provedor pago: Google e HERE.

Nenhum teste aqui toca a rede. As respostas sao gravadas, no formato que
cada API documenta, e o que se verifica e o que o Log Rotas FAZ com elas.

Isso cobre a leitura das respostas e NAO cobre a conversa de rede real —
nao ha chave disponivel para exercitar as duas APIs de verdade. A limitacao
esta escrita no topo de cada adaptador, e nao deve ser esquecida: na
primeira vez que uma chave for configurada, confira um endereco conhecido
na tela.

O caso que mais importa aqui e a distincao entre "o provedor respondeu que
nao existe" e "o provedor nao respondeu". Trata-los igual mandaria a equipe
reescrever enderecos que estavam certos enquanto o problema era a cota.
"""

from __future__ import annotations

import httpx
import pytest

from app.core.enums import GeocodePrecision, GeocodeStatus
from app.geocoding.google import GoogleProvider
from app.geocoding.here import HereProvider


def responder(payload: dict, codigo: int = 200):
    """Transporte falso que devolve sempre a mesma resposta."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(codigo, json=payload)

    return handler


@pytest.fixture
def com_resposta(monkeypatch):
    # A classe real precisa ser guardada ANTES da troca: chamar httpx.Client
    # de dentro do substituto chamaria o proprio substituto, e o teste
    # morreria em recursao antes de exercitar coisa nenhuma.
    ClientReal = httpx.Client

    def aplicar(payload: dict, codigo: int = 200):
        def criar(*args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(responder(payload, codigo))
            return ClientReal(*args, **kwargs)

        monkeypatch.setattr("httpx.Client", criar)

    return aplicar


# --------------------------------------------------------------------------- #
# Google
# --------------------------------------------------------------------------- #
def _google(location_type: str, *, parcial: bool = False, quantos: int = 1) -> dict:
    item = {
        "formatted_address": "Av. Calogeras, 1500 - Centro, Campo Grande - MS",
        "geometry": {
            "location": {"lat": -20.46312, "lng": -54.61055},
            "location_type": location_type,
        },
    }
    if parcial:
        item["partial_match"] = True
    return {"status": "OK", "results": [item] * quantos}


def test_google_rooftop_e_exato(com_resposta) -> None:
    """ROOFTOP e o Google dizendo que o ponto E o endereco.

    E o unico caso que dispensa conferencia humana — e e exatamente o que
    se esta comprando ao trocar o Nominatim por ele.
    """
    com_resposta(_google("ROOFTOP"))

    r = GoogleProvider(chave="x").geocode("Avenida Calogeras, 1500")

    assert r.status == GeocodeStatus.OK.value
    assert r.precision == GeocodePrecision.EXATO
    assert r.latitude == -20.46312


def test_google_interpolado_nao_e_exato(com_resposta) -> None:
    """RANGE_INTERPOLATED e estimativa entre os numeros das pontas da quadra.

    Cai perto, e perto nao e o portao. Aceitar como exato seria repetir o
    defeito que o Nominatim causava — so que com uma fatura junto.
    """
    com_resposta(_google("RANGE_INTERPOLATED"))

    r = GoogleProvider(chave="x").geocode("Avenida Calogeras, 1500")

    assert r.precision == GeocodePrecision.RUA
    assert r.precision is not GeocodePrecision.EXATO


def test_google_partial_match_vira_ambiguo(com_resposta) -> None:
    """`partial_match` e o Google avisando que nao casou o endereco inteiro.

    Tipicamente o numero nao existe naquela via. Gravar como certo seria
    transformar a duvida dele em certeza nossa.
    """
    com_resposta(_google("ROOFTOP", parcial=True))

    r = GoogleProvider(chave="x").geocode("Avenida Inexistente, 99999")

    assert r.status == GeocodeStatus.AMBIGUO.value
    assert r.latitude is None


def test_google_zero_results_e_nao_encontrado(com_resposta) -> None:
    com_resposta({"status": "ZERO_RESULTS", "results": []})

    r = GoogleProvider(chave="x").geocode("Rua que nao existe, 1")

    assert r.status == GeocodeStatus.FALHOU.value


@pytest.mark.parametrize(
    "status", ["OVER_QUERY_LIMIT", "REQUEST_DENIED", "INVALID_REQUEST", "UNKNOWN_ERROR"]
)
def test_google_falha_de_servico_nao_e_endereco_errado(com_resposta, status) -> None:
    """A distincao que evita trabalho inutil.

    O Google devolve HTTP 200 com o erro no corpo. Olhar so o codigo HTTP
    faria "a cota acabou" virar "endereco nao encontrado", e o endereco
    cairia na fila pedindo correcao — quando o que precisava de correcao
    era a fatura. Erro de provedor tambem nao entra no cache.
    """
    com_resposta({"status": status, "results": []})

    r = GoogleProvider(chave="x").geocode("Avenida Calogeras, 1500")

    assert r.status == "ERRO_PROVEDOR"
    assert r.error


def test_google_sem_chave_recusa_de_imediato() -> None:
    with pytest.raises(ValueError, match="GEOCODING_PROVIDER_KEY"):
        GoogleProvider(chave="")


# --------------------------------------------------------------------------- #
# HERE
# --------------------------------------------------------------------------- #
def _here(result_type: str, numero: str | None = None, quantos: int = 1) -> dict:
    item = {
        "title": "Av. Calogeras 1500",
        "resultType": result_type,
        "address": {"label": "Av. Calogeras, 1500, Campo Grande - MS, Brasil"},
        "position": {"lat": -20.46312, "lng": -54.61055},
    }
    if numero:
        item["houseNumberType"] = numero
    return {"items": [item] * quantos}


def test_here_endereco_da_base_e_exato(com_resposta) -> None:
    """`PA` (point address) quer dizer que o endereco esta na base da HERE."""
    com_resposta(_here("houseNumber", "PA"))

    r = HereProvider(chave="x").geocode("Avenida Calogeras, 1500")

    assert r.status == GeocodeStatus.OK.value
    assert r.precision == GeocodePrecision.EXATO


def test_here_interpolado_nao_e_exato(com_resposta) -> None:
    """Mesma regra do Google: estimado na quadra nao e o portao."""
    com_resposta(_here("houseNumber", "interpolated"))

    r = HereProvider(chave="x").geocode("Avenida Calogeras, 1500")

    assert r.precision == GeocodePrecision.RUA


def test_here_so_a_rua_pede_confirmacao(com_resposta) -> None:
    com_resposta(_here("street"))

    r = HereProvider(chave="x").geocode("Avenida Calogeras")

    assert r.precision == GeocodePrecision.RUA


def test_here_sem_itens_e_nao_encontrado(com_resposta) -> None:
    com_resposta({"items": []})

    r = HereProvider(chave="x").geocode("Rua que nao existe, 1")

    assert r.status == GeocodeStatus.FALHOU.value


@pytest.mark.parametrize(
    ("codigo", "trecho"), [(429, "cota"), (401, "chave"), (403, "chave"), (500, "500")]
)
def test_here_falha_de_servico_nao_e_endereco_errado(com_resposta, codigo, trecho) -> None:
    """Cota estourada e chave invalida precisam de acoes diferentes, e
    nenhuma das duas e "corrija o endereco"."""
    com_resposta({}, codigo)

    r = HereProvider(chave="x").geocode("Avenida Calogeras, 1500")

    assert r.status == "ERRO_PROVEDOR"
    assert trecho in r.error.lower()


def test_here_varios_candidatos_imprecisos_viram_ambiguo(com_resposta) -> None:
    """Varias respostas de nivel de rua significam que o provedor nao sabe
    qual e. Devolver a primeira seria escolher no escuro."""
    com_resposta(_here("street", quantos=3))

    r = HereProvider(chave="x").geocode("Rua Bahia")

    assert r.status == GeocodeStatus.AMBIGUO.value
    assert len(r.candidatos) == 3


def test_here_sem_chave_recusa_de_imediato() -> None:
    with pytest.raises(ValueError, match="GEOCODING_PROVIDER_KEY"):
        HereProvider(chave="")
