"""Rastreamento ao vivo, previsão de chegada e navegação.

Nenhum teste toca a rede: a suíte roda com MATRIX_PROVIDER=haversine e sem
chave do Google (ver conftest). Onde o comportamento com o OSRM importa, a
resposta dele é gravada.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.enums import Role
from app.models.base_location import BaseLocation
from app.models.delivery import Delivery
from app.models.driver import Driver
from app.models.route import Route, RouteStop, RouteStopDelivery
from app.models.vehicle import Vehicle
from app.routing import navegacao as nav
from app.routing import transito
from app.services import rastreamento
from app.services.rastreamento import calcular_previsao

ADMIN = "admin@britto.com.br"
MOTORISTA = "carlos@britto.com.br"
HOJE = date.today()
PONTOS = [(-20.4550, -54.6100), (-20.4800, -54.6400)]


@pytest.fixture(autouse=True)
def _limpa_memorias():
    rastreamento.limpar_caches()
    nav._cache_chegada.clear()
    yield
    rastreamento.limpar_caches()
    nav._cache_chegada.clear()


@pytest.fixture
def cenario(client: TestClient, criar_usuario, autenticar, db):
    """Uma rota confirmada de um motorista, ainda não iniciada."""
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    admin = autenticar(ADMIN)
    usuario = criar_usuario(email=MOTORISTA, role=Role.MOTORISTA, name="Carlos")

    base = BaseLocation(
        name="Loja", latitude=-20.4697, longitude=-54.6201,
        geocode_status="MANUAL", is_default=True,
    )
    veiculo = Vehicle(name="Caminhao", plate="AAA1A11", capacity_weight_kg=2000)
    motorista = Driver(name="Carlos", user_id=usuario.id)
    db.add_all([base, veiculo, motorista])
    db.commit()
    for i, (lat, lon) in enumerate(PONTOS):
        db.add(
            Delivery(
                address=f"Rua {i}, 100", recipient_name=f"Cliente {i}",
                latitude=lat, longitude=lon, geocode_status="MANUAL",
                scheduled_date=HOJE, status="PENDENTE", weight_kg=100,
            )
        )
    db.commit()

    plano = client.post(
        "/api/v1/planejamento/calcular",
        headers=admin,
        json={
            "date": HOJE.isoformat(), "base_id": base.id,
            "vehicle_ids": [veiculo.id], "driver_ids": [motorista.id],
            "limite_tempo_s": 3,
        },
    ).json()
    client.post(f"/api/v1/planejamento/{plano['id']}/confirmar", headers=admin, json={})

    cab = autenticar(MOTORISTA)
    rota = client.get("/api/v1/motorista/rotas", headers=cab).json()[0]
    return {"admin": admin, "motorista": cab, "rota": rota}


def _ponto(lat=-20.46, lon=-54.62, *, segundos_atras=0, **extra):
    quando = datetime.now(UTC) - timedelta(seconds=segundos_atras)
    return {"latitude": lat, "longitude": lon, "registrada_em": quando.isoformat(), **extra}


def _enviar(client, cenario, *pontos):
    return client.post(
        f"/api/v1/motorista/rotas/{cenario['rota']['id']}/posicoes",
        headers=cenario["motorista"],
        json={"posicoes": list(pontos)},
    )


def _iniciar(client, cenario):
    resposta = client.post(
        f"/api/v1/motorista/rotas/{cenario['rota']['id']}/iniciar", headers=cenario["motorista"]
    )
    assert resposta.status_code == 200, resposta.text


# --------------------------------------------------------------------------- #
# Posições
# --------------------------------------------------------------------------- #
def test_posicao_antes_de_iniciar_a_rota_e_descartada(client, cenario) -> None:
    """Privacidade: fora da execução da rota, a posição do motorista não é
    assunto do sistema."""
    corpo = _enviar(client, cenario, _ponto()).json()

    assert corpo["aceitas"] == 0
    assert corpo["motivos"] == {"rota não está em andamento": 1}


def test_posicoes_validas_sao_gravadas_e_as_ruins_contadas(client, cenario) -> None:
    """Um ponto ruim não derruba o lote — e não some em silêncio."""
    _iniciar(client, cenario)

    corpo = _enviar(
        client,
        cenario,
        _ponto(precisao_m=8, velocidade_mps=11.2, direcao_graus=90),
        _ponto(precisao_m=900),  # celular dentro do galpão
        _ponto(segundos_atras=-3600),  # relógio adiantado uma hora
        _ponto(segundos_atras=86400),  # de ontem, antes de a rota começar
    ).json()

    assert corpo["aceitas"] == 1
    assert corpo["descartadas"] == 3
    assert corpo["motivos"] == {
        "GPS impreciso": 1,
        "relógio do celular adiantado": 1,
        "anterior ao início da rota": 1,
    }


def test_posicao_repetida_e_sinal_de_vida_nao_linha_nova(client, cenario, db) -> None:
    """Parado, o GPS não produz leitura nova e o app reenvia a última.

    Não pode virar linha nova (o rastro encheria de pontos iguais) nem ser
    descartada (o painel mostraria "sem sinal" num caminhão só parado).
    """
    _iniciar(client, cenario)
    # 30 s: dentro da rota, que acabou de começar.
    ponto = _ponto(-20.4650, -54.6150, segundos_atras=30)
    _enviar(client, cenario, ponto)
    # O contato "envelhece", como se tivessem passado minutos.
    db.execute(
        rastreamento.RoutePosition.__table__.update().values(
            received_at=datetime.now(UTC) - timedelta(minutes=5)
        )
    )
    db.commit()

    corpo = _enviar(client, cenario, ponto).json()

    assert corpo == {"aceitas": 0, "repetidas": 1, "descartadas": 0, "motivos": {}}
    assert db.query(rastreamento.RoutePosition).count() == 1
    rota = client.get("/api/v1/painel/ao-vivo", headers=cenario["admin"]).json()["rotas"][0]
    # Vivo (contato renovado agora), com a idade real da medição.
    assert rota["situacao"] != "SEM_SINAL"
    assert rota["idade_s"] >= 25


def test_outro_motorista_nao_envia_posicao_para_a_minha_rota(
    client, cenario, criar_usuario, autenticar, db
) -> None:
    outro = criar_usuario(email="joana@britto.com.br", role=Role.MOTORISTA)
    db.add(Driver(name="Joana", user_id=outro.id))
    db.commit()
    _iniciar(client, cenario)

    resposta = client.post(
        f"/api/v1/motorista/rotas/{cenario['rota']['id']}/posicoes",
        headers=autenticar("joana@britto.com.br"),
        json={"posicoes": [_ponto()]},
    )

    assert resposta.status_code == 404


# --------------------------------------------------------------------------- #
# Painel ao vivo
# --------------------------------------------------------------------------- #
def test_painel_mostra_o_caminhao_na_ultima_posicao(client, cenario) -> None:
    _iniciar(client, cenario)
    _enviar(
        client,
        cenario,
        _ponto(-20.4650, -54.6150, segundos_atras=20, velocidade_mps=9),
        _ponto(-20.4640, -54.6140, segundos_atras=10, velocidade_mps=9, direcao_graus=45),
    )

    corpo = client.get("/api/v1/painel/ao-vivo", headers=cenario["admin"]).json()

    assert len(corpo["rotas"]) == 1
    rota = corpo["rotas"][0]
    assert rota["motorista"] == "Carlos"
    assert rota["situacao"] == "EM_MOVIMENTO"
    assert rota["posicao"]["latitude"] == pytest.approx(-20.464)
    assert rota["posicao"]["direcao_graus"] == 45
    assert len(rota["rastro"]) == 2
    assert rota["proxima"] is not None


def test_previsao_diz_de_onde_veio_o_tempo(client, cenario) -> None:
    """Sem OSRM (como na suíte), a previsão é linha reta — e diz isso."""
    _iniciar(client, cenario)
    _enviar(client, cenario, _ponto(-20.4650, -54.6150))

    rota = client.get("/api/v1/painel/ao-vivo", headers=cenario["admin"]).json()["rotas"][0]

    assert rota["previsao"]["fonte"] == "HAVERSINE"
    assert rota["previsao"]["estimada"] is True
    assert rota["previsao"]["aviso"]
    assert rota["proxima"]["chegada_prevista"] is not None


def test_sem_nenhuma_posicao_mostra_o_plano_e_avisa(client, cenario) -> None:
    """Horário do plano apresentado como previsão seria mentir."""
    _iniciar(client, cenario)

    rota = client.get("/api/v1/painel/ao-vivo", headers=cenario["admin"]).json()["rotas"][0]

    assert rota["situacao"] == "SEM_POSICAO"
    assert rota["previsao"]["fonte"] == "PLANEJADO"
    assert "planejamento" in rota["previsao"]["aviso"]


def test_sinal_perdido_aparece_como_sem_sinal(client, cenario, db) -> None:
    _iniciar(client, cenario)
    _enviar(client, cenario, _ponto())
    # Simula o celular calado há 5 minutos.
    db.execute(
        rastreamento.RoutePosition.__table__.update().values(
            received_at=datetime.now(UTC) - timedelta(minutes=5)
        )
    )
    db.commit()

    rota = client.get("/api/v1/painel/ao-vivo", headers=cenario["admin"]).json()["rotas"][0]

    assert rota["situacao"] == "SEM_SINAL"


def test_sem_velocidade_do_gps_e_sem_deslocamento_esta_parado(client, cenario) -> None:
    """Visto no teste de navegador: GPS sem velocidade, caminhão na base, e o
    painel dizia "em movimento". Sem evidência de movimento, é parado."""
    _iniciar(client, cenario)
    _enviar(
        client, cenario,
        _ponto(-20.4650, -54.6150, segundos_atras=20),
        _ponto(-20.4650, -54.6150, segundos_atras=5),
    )

    rota = client.get("/api/v1/painel/ao-vivo", headers=cenario["admin"]).json()["rotas"][0]

    assert rota["situacao"] == "PARADO"


def test_sem_velocidade_do_gps_o_rastro_mostra_o_movimento(client, cenario) -> None:
    """~150 m em 15 s: 10 m/s, andando — mesmo sem o GPS informar."""
    _iniciar(client, cenario)
    _enviar(
        client, cenario,
        _ponto(-20.4650, -54.6150, segundos_atras=20),
        _ponto(-20.4637, -54.6150, segundos_atras=5),
    )

    rota = client.get("/api/v1/painel/ao-vivo", headers=cenario["admin"]).json()["rotas"][0]

    assert rota["situacao"] == "EM_MOVIMENTO"


def test_primeira_posicao_troca_o_plano_pela_previsao_na_hora(client, cenario) -> None:
    """A memória de 45 s não pode segurar "horário do plano" depois que a
    primeira posição chega — o caminhão já aparece no mapa."""
    _iniciar(client, cenario)
    antes = client.get("/api/v1/painel/ao-vivo", headers=cenario["admin"]).json()["rotas"][0]
    assert antes["previsao"]["fonte"] == "PLANEJADO"

    _enviar(client, cenario, _ponto(-20.4650, -54.6150))
    depois = client.get("/api/v1/painel/ao-vivo", headers=cenario["admin"]).json()["rotas"][0]

    assert depois["previsao"]["fonte"] != "PLANEJADO"


def test_motorista_nao_ve_o_painel_ao_vivo(client, cenario) -> None:
    resposta = client.get("/api/v1/painel/ao-vivo", headers=cenario["motorista"])
    assert resposta.status_code == 403


# --------------------------------------------------------------------------- #
# Navegação
# --------------------------------------------------------------------------- #
def test_navegacao_exige_rota_iniciada(client, cenario) -> None:
    resposta = client.get(
        f"/api/v1/motorista/rotas/{cenario['rota']['id']}/navegacao",
        headers=cenario["motorista"],
        params={"latitude": -20.46, "longitude": -54.62},
    )
    assert resposta.status_code == 422


def test_navegacao_leva_a_primeira_entrega_pendente(client, cenario) -> None:
    _iniciar(client, cenario)

    corpo = client.get(
        f"/api/v1/motorista/rotas/{cenario['rota']['id']}/navegacao",
        headers=cenario["motorista"],
        params={"latitude": -20.46, "longitude": -54.62},
    ).json()

    assert corpo["concluida"] is False
    assert corpo["parada"]["tipo"] == "ENTREGA"
    assert corpo["parada"]["entregas"] == 1
    # Sem OSRM: linha reta, sem manobras, e a resposta diz.
    assert corpo["estimada"] is True
    assert corpo["manobras"] == []
    assert corpo["aviso"]


# --------------------------------------------------------------------------- #
# A conta da previsão
# --------------------------------------------------------------------------- #
AGORA = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)  # 08:00 em Campo Grande


def _rota(*paradas) -> Route:
    rota = Route(date=date(2026, 9, 21))
    rota.stops = list(paradas)
    return rota


def _parada(id_, seq, tipo="ENTREGA", status="PENDENTE", *, janela=None, servico=600, **extra):
    parada = RouteStop(
        id=id_, sequence=seq, stop_type=tipo, status=status, label=f"P{id_}",
        address=f"Rua {id_}, 1", latitude=-20.46, longitude=-54.62,
        service_time_s=servico, **extra,
    )
    if janela:
        parada.items = [RouteStopDelivery(delivery=Delivery(time_window_start=janela))]
    return parada


def _rotear_fixo(*duracoes):
    def rotear(pontos):
        assert len(pontos) - 1 == len(duracoes)
        return nav.RotaNavegavel(
            pernas=[nav.Perna(distancia_m=1000, duracao_s=d) for d in duracoes],
            geometria=None, distancia_m=0, duracao_s=sum(duracoes),
            source=nav.MatrixSource.OSRM, estimada=False,
        )
    return rotear


def _prever(rota, posicao=(-20.46, -54.62), rotear=None, **extra):
    return calcular_previsao(
        rota, posicao, agora=AGORA, servico_padrao_s=3600,
        rotear=rotear, chegada=lambda s: (float(s.latitude), float(s.longitude)), **extra,
    )


def test_previsao_soma_deslocamento_e_tempo_de_servico() -> None:
    rota = _rota(
        _parada(1, 0, "BASE_SAIDA", "CONCLUIDA"),
        _parada(2, 1), _parada(3, 2), _parada(4, 3, "BASE_RETORNO", servico=None),
    )

    p = _prever(rota, rotear=_rotear_fixo(300, 600, 900))

    horas = {x.stop_id: x.chegada_prevista for x in p.paradas}
    assert horas[2] == AGORA + timedelta(seconds=300)
    # 300 de ida + 600 de serviço na parada 2 + 600 de ida
    assert horas[3] == AGORA + timedelta(seconds=1500)
    # + 600 de serviço na parada 3 + 900 até a base; base não tem serviço
    assert horas[4] == AGORA + timedelta(seconds=3000)
    assert p.termino_previsto == horas[4]


def test_chegar_antes_da_janela_espera_o_cliente() -> None:
    """Chegar às 08:05 num cliente que abre às 09:00 não adianta a rota:
    o caminhão espera, e a espera empurra todo o resto."""
    rota = _rota(_parada(2, 1, janela=time(9, 0)), _parada(3, 2))

    p = _prever(rota, rotear=_rotear_fixo(300, 300))

    primeira, segunda = p.paradas
    assert primeira.espera_s == 55 * 60
    # abre 09:00 + 10 min de serviço + 5 min de ida = 09:15 (13:15 UTC)
    assert segunda.chegada_prevista == datetime(2026, 9, 21, 13, 15, tzinfo=UTC)


def test_motorista_na_parada_desconta_o_servico_ja_feito() -> None:
    rota = _rota(
        _parada(2, 1, status="CHEGOU", arrived_at=AGORA - timedelta(minutes=4)),
        _parada(3, 2),
    )

    p = _prever(rota, rotear=_rotear_fixo(300))

    # 10 min de serviço, 4 já passaram: sai em 6 min, chega 5 min depois.
    assert p.paradas[1].chegada_prevista == AGORA + timedelta(minutes=11)


def test_transito_multiplica_o_deslocamento_nao_o_servico() -> None:
    rota = _rota(_parada(2, 1), _parada(3, 2))

    p = _prever(rota, rotear=_rotear_fixo(600, 600), fator_transito=1.5)

    assert p.paradas[0].chegada_prevista == AGORA + timedelta(seconds=900)
    # 900 + 600 de serviço (sem fator) + 900
    assert p.paradas[1].chegada_prevista == AGORA + timedelta(seconds=2400)
    assert p.com_transito is True
    assert p.fonte == "OSRM+TRANSITO"


def test_atraso_e_comparado_com_o_planejado() -> None:
    rota = _rota(_parada(2, 1, estimated_arrival=AGORA))

    p = _prever(rota, rotear=_rotear_fixo(1200))

    assert p.paradas[0].atraso_s == 1200


def test_previsao_nao_recalcula_a_cada_consulta(client, cenario, monkeypatch) -> None:
    """O painel consulta a cada 5 s. Recalcular a cada consulta martelaria o
    serviço de rotas e, com trânsito, a conta do Google."""
    _iniciar(client, cenario)
    _enviar(client, cenario, _ponto(-20.4650, -54.6150))
    chamadas = []
    original = nav.rota
    monkeypatch.setattr(nav, "rota", lambda *a, **k: chamadas.append(1) or original(*a, **k))

    for _ in range(3):
        client.get("/api/v1/painel/ao-vivo", headers=cenario["admin"])

    assert len(chamadas) == 1


# --------------------------------------------------------------------------- #
# Ponto de chegada e manobras
# --------------------------------------------------------------------------- #
def _ruas_proximas(monkeypatch, *ruas):
    monkeypatch.setattr(nav, "_osrm_ligado", lambda: True)
    monkeypatch.setattr(
        nav,
        "_get",
        lambda caminho, params: {
            "code": "Ok",
            "waypoints": [
                {"name": nome, "distance": dist, "location": [lon, lat]}
                for nome, dist, lat, lon in ruas
            ],
        },
    )


def test_chegada_pela_rua_do_endereco_e_nao_pela_de_tras(monkeypatch) -> None:
    """Caso medido em Campo Grande: o pino de "Rua Bahia, 500" fica mais
    perto da Rua Piratininga. Chegando por ela, a rota dava a volta no
    quarteirão."""
    _ruas_proximas(
        monkeypatch,
        ("Rua Piratininga", 18, -20.458124, -54.602339),
        ("Rua Bahia", 22, -20.45832, -54.6026),
    )

    ponto = nav.ponto_de_chegada(-20.45828, -54.60239, "Rua Bahia, 500, Itanhangá Park")

    assert ponto == (-20.45832, -54.6026)


def test_rua_do_endereco_longe_demais_nao_e_usada(monkeypatch) -> None:
    """Mesmo nome a 300 m é outro trecho da rua, não a entrada do lote."""
    _ruas_proximas(monkeypatch, ("Rua Bahia", 300, -20.46, -54.60))

    ponto = nav.ponto_de_chegada(-20.45828, -54.60239, "Rua Bahia, 500")

    assert ponto == (-20.45828, -54.60239)


@pytest.mark.parametrize(
    ("tipo", "mod", "rua", "saida", "frase"),
    [
        ("turn", "right", "Rua Bahia", None, "Vire à direita na Rua Bahia"),
        ("turn", "slight left", "Viaduto Moura", None,
         "Vire levemente à esquerda no Viaduto Moura"),
        ("roundabout", "right", "Avenida Mato Grosso", 2,
         "Na rotatória, pegue a 2ª saída para a Avenida Mato Grosso"),
        ("new name", "straight", "Avenida Ricardo Brandão", None,
         "Continue pela Avenida Ricardo Brandão"),
        ("turn", "uturn", "Avenida Afonso Pena", None, "Faça o retorno na Avenida Afonso Pena"),
        ("arrive", "right", "", None, "Destino à direita"),
    ],
)
def test_manobras_em_portugues(tipo, mod, rua, saida, frase) -> None:
    assert nav.instrucao(tipo, mod, rua, saida) == frase


# --------------------------------------------------------------------------- #
# Trânsito
# --------------------------------------------------------------------------- #
def test_fator_de_transito_tem_limites() -> None:
    """Fator 10 faria a previsão dizer "chega amanhã": mais provável erro de
    dado do que trânsito."""
    assert transito.fator(473, 240) == pytest.approx(1.97, abs=0.01)
    assert transito.fator(5000, 100) == transito.FATOR_MAXIMO
    assert transito.fator(0, 100) == 1.0


@pytest.fixture
def google(monkeypatch):
    ClientReal = httpx.Client
    estado = {"codigo": 200, "corpo": {}}

    def criar(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(
            lambda r: httpx.Response(estado["codigo"], json=estado["corpo"])
        )
        return ClientReal(*args, **kwargs)

    monkeypatch.setattr("httpx.Client", criar)
    monkeypatch.setattr(transito, "_cliente", None)
    monkeypatch.setattr(transito, "disponivel", lambda: True)
    return estado


def test_transito_le_as_pernas_do_google(google) -> None:
    # Resposta real da Routes API em 21/09/2026, Centro -> Rua Bahia.
    google["corpo"] = {"routes": [{"legs": [
        {"distanceMeters": 2513, "duration": "473s", "staticDuration": "486s"}]}]}

    tempo = transito.consultar([(-20.4635, -54.6180), (-20.45832, -54.6026)])

    assert tempo.duracoes_s == [473]
    assert tempo.duracoes_livres_s == [486]


@pytest.mark.parametrize(
    ("razao", "trecho"),
    [("SERVICE_DISABLED", "não está ativada"), ("BILLING_DISABLED", "faturamento")],
)
def test_recusa_do_google_diz_a_causa(google, razao, trecho) -> None:
    google["codigo"] = 403
    google["corpo"] = {"error": {"status": "PERMISSION_DENIED", "message": "x",
                                 "details": [{"reason": razao}]}}

    with pytest.raises(transito.TransitoIndisponivel, match=trecho):
        transito.consultar([(-20.46, -54.62), (-20.45, -54.60)])
