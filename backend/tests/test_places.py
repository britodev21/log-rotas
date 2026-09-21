"""Busca com sugestoes (Google Places) e a origem do ponto gravado.

Nenhum teste toca a rede. O que se verifica e o que o Log Rotas faz com as
respostas — e, acima de tudo, que o navegador NAO consegue fazer uma
coordenada passar por exata so dizendo que ela veio do Google.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.enums import GeocodePrecision, Role
from app.geocoding import places
from app.geocoding.service import guardar_lugar

ADMIN = "admin@britto.com.br"
HOJE = date.today().isoformat()
PONTO = (-20.46312, -54.61055)


@pytest.fixture
def admin(client: TestClient, criar_usuario, autenticar):
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    return autenticar(ADMIN)


@pytest.fixture(autouse=True)
def _limpa_estado_do_modulo():
    # A pausa apos recusa e a conexao mantida sao estado de processo. Sem
    # zerar, um teste herdaria o transporte falso do anterior.
    places._geocoding_recusado_em = None
    places._cliente = None
    yield
    places._geocoding_recusado_em = None
    places._cliente = None


def _lugar(precisao=GeocodePrecision.EXATO, tipo_ponto="ROOFTOP", place_id="abc123"):
    return places.Lugar(
        place_id=place_id,
        endereco_formatado="Av. Calogeras, 1500 - Centro, Campo Grande - MS, 79002-000",
        latitude=PONTO[0],
        longitude=PONTO[1],
        precision=precisao,
        tipo_ponto=tipo_ponto,
        logradouro="Avenida Calogeras",
        numero="1500",
        bairro="Centro",
        cidade="Campo Grande",
        uf="MS",
        cep="79002-000",
    )


def _criar_entrega(client, admin, **extra):
    corpo = {
        "recipient_name": "Teste",
        "address": "Avenida Calogeras, 1500, Centro, Campo Grande - MS",
        "latitude": PONTO[0],
        "longitude": PONTO[1],
        "scheduled_date": HOJE,
        **extra,
    }
    resposta = client.post("/api/v1/entregas", headers=admin, json=corpo)
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


# --------------------------------------------------------------------------- #
# A origem do ponto e decidida pelo servidor
# --------------------------------------------------------------------------- #
def test_lugar_rooftop_do_google_entra_como_exato(client, admin, db) -> None:
    """O caso que a integracao existe para produzir: escolheu no Google, o
    Google provou que e o telhado, entra em rota sem conferencia."""
    guardar_lugar(db, _lugar())
    db.commit()

    entrega = _criar_entrega(client, admin, google_place_id="abc123")

    assert entrega["geocode_status"] == "OK"
    assert entrega["geocode_precision"] == "EXATO"


def test_navegador_nao_consegue_fingir_exato(client, admin) -> None:
    """Um place_id que o servidor nunca viu nao prova nada.

    Se a precisao viesse do navegador, qualquer cliente da API gravaria uma
    coordenada qualquer como EXATO e passaria pela barreira do planejamento.
    """
    entrega = _criar_entrega(client, admin, google_place_id="inventado")

    assert entrega["geocode_precision"] == "RUA"


def test_coordenada_diferente_da_do_google_nao_herda_a_precisao(client, admin, db) -> None:
    """O place_id e real, mas o ponto enviado nao e o que o Google devolveu.

    A prova do Google vale para AQUELE ponto. Qualquer outro volta a ser
    aproximado — se a pessoa mexeu no pino de proposito, isso e
    `ponto_confirmado`, e vira MANUAL.
    """
    guardar_lugar(db, _lugar())
    db.commit()

    entrega = _criar_entrega(
        client, admin, google_place_id="abc123", latitude=-20.47, longitude=-54.62
    )

    assert entrega["geocode_precision"] == "RUA"


def test_lugar_interpolado_do_google_pede_confirmacao(client, admin, db) -> None:
    """Achou o numero, mas o ponto e estimado entre as pontas da quadra.
    O pino ja comeca no lugar certo; a confirmacao vira um olhar."""
    guardar_lugar(db, _lugar(GeocodePrecision.RUA, "RANGE_INTERPOLATED"))
    db.commit()

    entrega = _criar_entrega(client, admin, google_place_id="abc123")

    assert entrega["geocode_precision"] == "RUA"


def test_mexer_no_pino_depois_do_google_vira_manual(client, admin, db) -> None:
    guardar_lugar(db, _lugar())
    db.commit()

    entrega = _criar_entrega(
        client,
        admin,
        google_place_id="abc123",
        latitude=-20.4632,
        longitude=-54.6106,
        ponto_confirmado=True,
    )

    assert entrega["geocode_status"] == "MANUAL"


def test_cliente_com_ponto_exato_passa_a_prova_para_a_entrega(client, admin, db) -> None:
    """Sem isto, cada pedido de um cliente ja resolvido pelo Google voltaria
    a pedir conferencia — a prova ficaria no cliente e nao viajaria."""
    guardar_lugar(db, _lugar())
    db.commit()
    cliente = client.post(
        "/api/v1/clientes",
        headers=admin,
        json={
            "name": "Marcenaria Alfa",
            "address": "Avenida Calogeras, 1500",
            "latitude": PONTO[0],
            "longitude": PONTO[1],
            "google_place_id": "abc123",
        },
    ).json()
    assert cliente["geocode_precision"] == "EXATO"

    entrega = client.post(
        "/api/v1/entregas",
        headers=admin,
        json={"customer_id": cliente["id"], "scheduled_date": HOJE},
    ).json()

    assert entrega["geocode_precision"] == "EXATO"


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #
def test_recursos_sem_chave_desliga_o_autocomplete(client, admin, monkeypatch) -> None:
    monkeypatch.setattr(places, "chave", lambda: "")

    assert client.get("/api/v1/geocodificacao/recursos", headers=admin).json() == {
        "autocomplete": False
    }


def test_sugestoes_sem_chave_responde_503_com_instrucao(client, admin, monkeypatch) -> None:
    """503, nao 500: a mensagem precisa dizer o que configurar."""
    monkeypatch.setattr(places, "chave", lambda: "")

    resposta = client.get(
        "/api/v1/geocodificacao/sugestoes",
        headers=admin,
        params={"texto": "Afonso Pena", "sessao": "12345678-abcd"},
    )

    assert resposta.status_code == 503
    assert "GOOGLE_MAPS_API_KEY" in resposta.json()["mensagem"]


def test_rota_do_lugar_nao_e_engolida_pela_generica(client, admin, monkeypatch) -> None:
    """`/lugar/<id>` casa com `/{tipo}/{registro_id}`.

    Registrada depois da generica, a rota responderia 405 — o mesmo defeito
    que ja aconteceu com `/cep/<cep>`.
    """
    monkeypatch.setattr(places, "detalhar", lambda place_id, sessao: _lugar(place_id=place_id))

    resposta = client.get("/api/v1/geocodificacao/lugar/abc123", headers=admin)

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["numero"] == "1500"
    assert corpo["precision"] == "EXATO"


def test_motorista_nao_usa_a_busca(client, criar_usuario, autenticar) -> None:
    criar_usuario(email="mot@britto.com.br", role=Role.MOTORISTA)
    cabecalho = autenticar("mot@britto.com.br")

    resposta = client.get("/api/v1/geocodificacao/recursos", headers=cabecalho)

    assert resposta.status_code == 403


# --------------------------------------------------------------------------- #
# Leitura das respostas do Google
# --------------------------------------------------------------------------- #
DETALHE = {
    "id": "abc123",
    "formattedAddress": "Av. Calogeras, 1500 - Centro, Campo Grande - MS, 79002-000, Brasil",
    "location": {"latitude": PONTO[0], "longitude": PONTO[1]},
    "types": ["street_address"],
    "addressComponents": [
        {"longText": "1500", "shortText": "1500", "types": ["street_number"]},
        {"longText": "Avenida Calogeras", "shortText": "Av. Calogeras", "types": ["route"]},
        {"longText": "Centro", "shortText": "Centro",
         "types": ["sublocality_level_1", "sublocality"]},
        {"longText": "Campo Grande", "shortText": "Campo Grande",
         "types": ["administrative_area_level_2", "political"]},
        {"longText": "Mato Grosso do Sul", "shortText": "MS",
         "types": ["administrative_area_level_1", "political"]},
        {"longText": "79002-000", "shortText": "79002-000", "types": ["postal_code"]},
    ],
}


@pytest.fixture
def google(monkeypatch):
    """Responde como o Google: detalhe pelo Places e tipo do ponto pela
    Geocoding API. `geocoding` controla o que a segunda devolve."""
    ClientReal = httpx.Client
    estado = {"geocoding": {"status": "OK", "results": [
        {"geometry": {"location_type": "ROOFTOP"}}]}, "chamadas_geocoding": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if "places.googleapis.com" in request.url.host:
            return httpx.Response(200, json=DETALHE)
        estado["chamadas_geocoding"] += 1
        return httpx.Response(200, json=estado["geocoding"])

    def criar(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return ClientReal(*args, **kwargs)

    monkeypatch.setattr("httpx.Client", criar)
    monkeypatch.setattr(places, "chave", lambda: "x")
    return estado


def test_detalhe_le_os_componentes_do_endereco(google) -> None:
    lugar = places.detalhar("abc123", "sessao-1")

    assert lugar.logradouro == "Avenida Calogeras"
    assert lugar.numero == "1500"
    assert lugar.bairro == "Centro"
    # Em Campo Grande o Google as vezes poe a cidade so no nivel 2.
    assert lugar.cidade == "Campo Grande"
    assert lugar.uf == "MS"
    assert lugar.cep == "79002-000"


def test_rooftop_vira_exato(google) -> None:
    lugar = places.detalhar("abc123", "sessao-1")

    assert lugar.tipo_ponto == "ROOFTOP"
    assert lugar.precision == GeocodePrecision.EXATO


def test_interpolado_vira_rua(google) -> None:
    google["geocoding"] = {"status": "OK", "results": [
        {"geometry": {"location_type": "RANGE_INTERPOLATED"}}]}

    lugar = places.detalhar("abc123", "sessao-1")

    assert lugar.precision == GeocodePrecision.RUA


def test_sem_geocoding_api_nao_adivinha(google) -> None:
    """Geocoding API nao ativada: nao ha como provar que e o telhado.

    O endereco continua certo, com numero — so o ponto deixa de ser
    dispensado de conferencia. E a pausa evita repetir a chamada recusada
    a cada escolha.
    """
    google["geocoding"] = {"status": "REQUEST_DENIED", "error_message": "not activated"}

    primeiro = places.detalhar("abc123", "sessao-1")
    segundo = places.detalhar("abc123", "sessao-2")

    assert primeiro.tipo_ponto is None
    assert primeiro.precision == GeocodePrecision.RUA
    assert primeiro.numero == "1500"
    assert segundo.precision == GeocodePrecision.RUA
    assert google["chamadas_geocoding"] == 1
