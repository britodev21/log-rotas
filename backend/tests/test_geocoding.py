"""Geocodificacao.

Nenhum teste aqui toca a rede. Um provedor falso devolve o desfecho que o
teste quer exercitar — o que se esta verificando nao e se o Nominatim
funciona (nao e nosso codigo), e sim o que o Log Rotas FAZ com cada resposta
possivel: o que grava, o que se recusa a gravar e o que manda para revisao.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.enums import GeocodePrecision, GeocodeStatus, Role
from app.geocoding import service as geo_service
from app.geocoding.base import Candidato, GeocodeResult
from app.geocoding.service import GeocodingService, chave_cache, normalizar_endereco
from app.models.customer import Customer
from app.models.geocode_cache import GeocodeCache

ADMIN = "admin@britto.com.br"
HOJE = date.today().isoformat()


class ProviderFalso:
    """Devolve sempre o mesmo resultado e conta quantas vezes foi chamado."""

    nome = "falso"

    def __init__(self, resultado: GeocodeResult) -> None:
        self.resultado = resultado
        self.chamadas = 0

    def geocode(self, endereco: str) -> GeocodeResult:
        self.chamadas += 1
        return self.resultado


def resultado_ok(lat=-20.4697, lon=-54.6201) -> GeocodeResult:
    return GeocodeResult.ok(
        latitude=lat,
        longitude=lon,
        precision=GeocodePrecision.EXATO,
        normalized_address="Rua Teste, 100 - Campo Grande",
        provider="falso",
        raw={"lat": lat},
    )


@pytest.fixture
def admin(client: TestClient, criar_usuario, autenticar):
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    return autenticar(ADMIN)


@pytest.fixture
def cliente(db):
    c = Customer(name="Marcenaria Teste", address="Rua Teste, 100")
    db.add(c)
    db.commit()
    return c


# --------------------------------------------------------------------------- #
# Normalizacao e cache
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Av. Afonso Pena, 1500", "av afonso pena 1500"),
        ("AVENIDA  AFONSO   PENA 1500", "avenida afonso pena 1500"),
        ("Rua São João, 45", "rua sao joao 45"),
        ("  Rua  Bahia , 10 ", "rua bahia 10"),
    ],
)
def test_normalizacao_de_endereco(entrada, esperado) -> None:
    assert normalizar_endereco(entrada) == esperado


def test_mesma_chave_para_escritas_diferentes_do_mesmo_endereco() -> None:
    """Cada consulta desperdicada custa um segundo do recurso mais escasso."""
    assert chave_cache("Rua São João, 45") == chave_cache("rua sao joao   45")
    assert chave_cache("Rua São João, 45") != chave_cache("Rua Sao Joao, 46")


def test_segunda_consulta_sai_do_cache(db) -> None:
    provider = ProviderFalso(resultado_ok())
    servico = GeocodingService(db, provider)

    servico.geocodificar("Rua Teste, 100")
    servico.geocodificar("rua teste 100")  # mesma coisa, escrita diferente

    assert provider.chamadas == 1


def test_erro_de_provedor_nao_entra_no_cache(db) -> None:
    """Falha de rede e temporaria. Guardar transformaria um problema de
    minutos num endereco permanentemente quebrado."""
    provider = ProviderFalso(GeocodeResult.erro("timeout", provider="falso"))
    servico = GeocodingService(db, provider)

    servico.geocodificar("Rua Teste, 100")

    assert db.get(GeocodeCache, chave_cache("Rua Teste, 100")) is None


def test_endereco_nao_encontrado_entra_no_cache(db) -> None:
    """Diferente de erro de rede: o provedor respondeu, e a resposta foi
    "nao existe". Reconsultar toda vez gastaria o limite a toa."""
    provider = ProviderFalso(GeocodeResult.nao_encontrado(provider="falso"))
    servico = GeocodingService(db, provider)

    servico.geocodificar("Rua Inexistente, 9999")

    guardado = db.get(GeocodeCache, chave_cache("Rua Inexistente, 9999"))
    assert guardado is not None
    assert guardado.status == GeocodeStatus.FALHOU.value


# --------------------------------------------------------------------------- #
# O que o sistema faz com cada desfecho
# --------------------------------------------------------------------------- #
def test_sucesso_grava_coordenada_e_precisao(db, cliente) -> None:
    GeocodingService(db, ProviderFalso(resultado_ok())).aplicar(cliente)

    assert cliente.geocode_status == GeocodeStatus.OK.value
    assert float(cliente.latitude) == -20.4697
    assert cliente.geocode_precision == GeocodePrecision.EXATO.value
    assert cliente.geocoded_at is not None


def test_ambiguo_NAO_grava_coordenada(db, cliente) -> None:
    """A regra mais importante deste modulo.

    Escolher sozinho entre candidatos e o caminho mais curto para entregar
    no lugar errado — e, pior, sem ninguem perceber. Fica para o humano.
    """
    ambiguo = GeocodeResult.ambiguo(
        [
            Candidato(-20.1, -54.1, "Rua Bahia, Centro"),
            Candidato(-20.9, -54.9, "Rua Bahia, Tiradentes"),
        ],
        provider="falso",
    )

    GeocodingService(db, ProviderFalso(ambiguo)).aplicar(cliente)

    assert cliente.geocode_status == GeocodeStatus.AMBIGUO.value
    assert cliente.latitude is None
    assert cliente.longitude is None


def test_falha_registra_o_motivo(db, cliente) -> None:
    provider = ProviderFalso(GeocodeResult.nao_encontrado(provider="falso"))

    GeocodingService(db, provider).aplicar(cliente)

    assert cliente.geocode_status == GeocodeStatus.FALHOU.value
    assert cliente.geocode_error


def test_pino_manual_nao_e_sobrescrito(db, cliente) -> None:
    """Sem esta regra, a proxima rodada automatica desfaria a correcao que o
    administrador fez a mao."""
    servico = GeocodingService(db, ProviderFalso(resultado_ok()))
    servico.definir_coordenada("cliente", cliente.id, -20.1234, -54.5678)

    provider = ProviderFalso(resultado_ok(lat=-99.0, lon=-99.0))
    GeocodingService(db, provider).aplicar(cliente)

    assert cliente.geocode_status == GeocodeStatus.MANUAL.value
    assert float(cliente.latitude) == -20.1234
    assert provider.chamadas == 0  # nem consultou o provedor


def test_forcar_sobrescreve_o_pino_manual(db, cliente) -> None:
    servico = GeocodingService(db, ProviderFalso(resultado_ok()))
    servico.definir_coordenada("cliente", cliente.id, -20.1234, -54.5678)

    GeocodingService(db, ProviderFalso(resultado_ok())).aplicar(cliente, forcar=True)

    assert cliente.geocode_status == GeocodeStatus.OK.value
    assert float(cliente.latitude) == -20.4697


def test_lote_nao_para_no_primeiro_erro(db) -> None:
    """Numa importacao de cinquenta enderecos, parar no primeiro obrigaria a
    recomecar tudo."""
    clientes = [Customer(name=f"Cliente {i}", address=f"Rua {i}, 10") for i in range(4)]
    for c in clientes:
        db.add(c)
    db.commit()

    provider = ProviderFalso(GeocodeResult.nao_encontrado(provider="falso"))
    contagem = GeocodingService(db, provider).geocodificar_lote(clientes)

    assert contagem["falhou"] == 4
    assert all(c.geocode_status == GeocodeStatus.FALHOU.value for c in clientes)


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
def test_coordenada_manual_pela_api(client: TestClient, admin, cliente) -> None:
    resposta = client.put(
        f"/api/v1/geocodificacao/cliente/{cliente.id}/coordenada",
        headers=admin,
        json={"latitude": -20.4697, "longitude": -54.6201},
    )

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "MANUAL"


def test_coordenada_fora_da_faixa_e_recusada(client: TestClient, admin, cliente) -> None:
    resposta = client.put(
        f"/api/v1/geocodificacao/cliente/{cliente.id}/coordenada",
        headers=admin,
        json={"latitude": 200, "longitude": -54.6},
    )
    assert resposta.status_code == 422


def test_fila_de_pendentes_lista_quem_precisa_de_atencao(
    client: TestClient, admin, cliente
) -> None:
    resposta = client.get("/api/v1/geocodificacao/pendentes", headers=admin)

    assert resposta.status_code == 200
    pendentes = resposta.json()
    assert any(p["tipo"] == "cliente" and p["id"] == cliente.id for p in pendentes)


def test_fila_ignora_quem_ja_tem_coordenada(client: TestClient, admin, cliente, db) -> None:
    GeocodingService(db, ProviderFalso(resultado_ok())).aplicar(cliente)
    db.commit()

    pendentes = client.get("/api/v1/geocodificacao/pendentes", headers=admin).json()

    assert not any(p["id"] == cliente.id and p["tipo"] == "cliente" for p in pendentes)


def test_lote_pela_api_usa_provedor_configurado(
    client: TestClient, admin, cliente, monkeypatch
) -> None:
    provider = ProviderFalso(resultado_ok())
    monkeypatch.setattr(geo_service, "construir_provider", lambda: provider)

    resposta = client.post(
        "/api/v1/geocodificacao/lote", headers=admin, json={"tipo": "cliente", "limite": 10}
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["ok"] == 1
    assert corpo["processados"] == 1


def test_motorista_nao_geocodifica(client: TestClient, criar_usuario, autenticar) -> None:
    criar_usuario(email="mot@britto.com.br", role=Role.MOTORISTA)
    cabecalho = autenticar("mot@britto.com.br")
    assert client.get("/api/v1/geocodificacao/pendentes", headers=cabecalho).status_code == 403


# --------------------------------------------------------------------------- #
# Ordem das rotas
# --------------------------------------------------------------------------- #
def test_cep_nao_e_engolido_pela_rota_generica(client: TestClient, admin) -> None:
    """Regressao de um bug real.

    `/geocodificacao/cep/79002000` casa com `/geocodificacao/{tipo}/{registro_id}`
    — com tipo="cep". Quando a rota generica estava registrada primeiro, o
    FastAPI achava o caminho, nao achava o metodo e respondia 405, numa falha
    que nao parece ter relacao nenhuma com ordenacao de rotas.

    O teste nao consulta os Correios: um CEP com formato invalido ja separa
    os dois desfechos. 405 significa que a rota generica voltou a vir antes.
    """
    resposta = client.get("/api/v1/geocodificacao/cep/123", headers=admin)

    assert resposta.status_code != 405, (
        "a rota de CEP foi capturada por /{tipo}/{registro_id}; "
        "rotas de caminho fixo precisam ser registradas antes das genericas"
    )
    assert resposta.status_code == 422  # CEP com 3 digitos


def test_busca_nao_e_engolida_pela_rota_generica(client: TestClient, admin) -> None:
    resposta = client.get(
        "/api/v1/geocodificacao/buscar", headers=admin, params={"endereco": "x"}
    )
    assert resposta.status_code != 405
    assert resposta.status_code == 422  # menos de 3 caracteres


def test_cep_invalido_e_recusado_sem_consultar_os_correios(client: TestClient, admin) -> None:
    for invalido in ("123", "abcdefgh", "123456789012"):
        resposta = client.get(f"/api/v1/geocodificacao/cep/{invalido}", headers=admin)
        assert resposta.status_code == 422, invalido
