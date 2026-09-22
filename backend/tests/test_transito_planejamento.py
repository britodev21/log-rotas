"""Trânsito no planejamento: a cobertura dos pares, a matriz e o plano.

O Google não é chamado: `consultar` é trocado por um falso que devolve
tempos conhecidos e conta as chamadas. O que se verifica é o que o sistema
faz com a resposta — e com a falta dela.
"""

from __future__ import annotations

import random
from datetime import UTC, date, datetime, time, timedelta
from itertools import pairwise

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.enums import MatrixSource, Role
from app.models.base_location import BaseLocation
from app.models.delivery import Delivery
from app.models.trafego import TrafficLeg
from app.models.vehicle import Vehicle
from app.routing import transito
from app.routing.base import Ponto
from app.routing.haversine import HaversineProvider
from app.routing.matriz_transito import (
    PERNAS_POR_CONSULTA,
    MatrizComTransito,
    sequencias,
)
from app.routing.transito import TempoComTransito, TransitoIndisponivel

AMANHA = date.today() + timedelta(days=1)
PARTIDA = datetime.combine(AMANHA, time(11, 0), tzinfo=UTC)


def _pernas(seqs: list[list[int]]) -> list[tuple[int, int]]:
    return [(s[k], s[k + 1]) for s in seqs for k in range(len(s) - 1)]


# --------------------------------------------------------------------------- #
# Cobertura: passar por todos os pares com o menor número de chamadas
# --------------------------------------------------------------------------- #
def test_matriz_completa_cabe_no_minimo_de_chamadas() -> None:
    """21 pontos = 420 pares. Cada chamada mede 26: 17 chamadas, nenhuma a
    mais — o circuito de Euler passa por cada par exatamente uma vez."""
    n = 21
    arcos = [(a, b) for a in range(n) for b in range(n) if a != b]

    seqs = sequencias(arcos)

    assert len(seqs) == -(-len(arcos) // PERNAS_POR_CONSULTA) == 17
    assert sorted(_pernas(seqs)) == sorted(arcos)
    assert all(len(s) - 1 <= PERNAS_POR_CONSULTA for s in seqs)


def test_entrega_nova_num_plano_ja_medido_custa_duas_chamadas() -> None:
    """Recalcular com uma entrega a mais: só os pares dela, ida e volta."""
    nova, outros = 20, range(20)
    arcos = [(nova, x) for x in outros] + [(x, nova) for x in outros]

    seqs = sequencias(arcos)

    assert len(seqs) == 2
    assert set(_pernas(seqs)) == set(arcos)


@pytest.mark.parametrize("semente", range(8))
def test_qualquer_conjunto_de_pares_fica_coberto(semente: int) -> None:
    """Pares soltos (o que sobra do cache): todos medidos, nenhuma perna de
    um ponto para ele mesmo, nenhuma chamada acima do limite da API."""
    sorteio = random.Random(semente)
    n = sorteio.randint(2, 30)
    todos = [(a, b) for a in range(n) for b in range(n) if a != b]
    arcos = sorteio.sample(todos, sorteio.randint(1, len(todos)))

    seqs = sequencias(arcos)
    pernas = _pernas(seqs)

    assert set(arcos) <= set(pernas)
    assert all(a != b for a, b in pernas)
    assert all(2 <= len(s) <= PERNAS_POR_CONSULTA + 1 for s in seqs)


# --------------------------------------------------------------------------- #
# A matriz com trânsito
# --------------------------------------------------------------------------- #
class GoogleFalso:
    """Tempo = 3x a linha reta; distância = 1,5x. Conta as chamadas."""

    def __init__(self, falhar: int = 0) -> None:
        self.chamadas: list[tuple[list, datetime | None]] = []
        self.falhar = falhar
        self.hav = HaversineProvider()

    def __call__(self, pontos, partida=None):
        self.chamadas.append((pontos, partida))
        if len(self.chamadas) <= self.falhar:
            raise TransitoIndisponivel("a cota do Google acabou")
        pts = [Ponto(str(i), la, lo) for i, (la, lo) in enumerate(pontos)]
        m = self.hav.matriz(pts)
        pernas = range(len(pontos) - 1)
        return TempoComTransito(
            duracoes_s=[m.duracoes[k][k + 1] * 3 for k in pernas],
            duracoes_livres_s=[m.duracoes[k][k + 1] for k in pernas],
            distancias_m=[round(m.distancias[k][k + 1] * 1.5) for k in pernas],
        )


def _livre(n: int, *, repetir_primeiro: bool = False):
    sorteio = random.Random(n)

    def perto(centro: float) -> float:
        return centro + sorteio.uniform(-0.04, 0.04)

    pontos = [Ponto(str(i), perto(-20.46), perto(-54.62)) for i in range(n)]
    if repetir_primeiro:
        pontos.append(Ponto("mesmo-lugar", pontos[0].latitude, pontos[0].longitude))
    return HaversineProvider().matriz(pontos)


def test_troca_todos_os_tempos_pelos_do_google(db) -> None:
    livre = _livre(8)
    google = GoogleFalso()

    matriz, resumo = MatrizComTransito(db, google).aplicar(livre, PARTIDA)

    assert matriz.source == MatrixSource.GOOGLE_TRANSITO
    assert resumo.pares_por_fator == 0
    assert resumo.consultas == len(google.chamadas) == 3  # 56 pares / 26
    for i in range(8):
        for j in range(8):
            if i != j:
                assert matriz.duracoes[i][j] == pytest.approx(livre.duracoes[i][j] * 3, abs=3)
    assert resumo.fator == pytest.approx(3, rel=0.01)
    # A hora do turno chega ao Google.
    assert all(partida == PARTIDA for _, partida in google.chamadas)


def test_recalcular_o_mesmo_dia_nao_consulta_de_novo(db) -> None:
    livre = _livre(8)
    MatrizComTransito(db, GoogleFalso()).aplicar(livre, PARTIDA)
    segunda = GoogleFalso()

    matriz, resumo = MatrizComTransito(db, segunda).aplicar(livre, PARTIDA)

    assert segunda.chamadas == []
    assert resumo.pares_do_cache == 56
    assert matriz.source == MatrixSource.GOOGLE_TRANSITO


def test_outra_hora_de_partida_nao_usa_o_cache(db) -> None:
    """O trânsito das 8h não serve para as 17h."""
    livre = _livre(5)
    MatrizComTransito(db, GoogleFalso()).aplicar(livre, PARTIDA)
    tarde = GoogleFalso()

    MatrizComTransito(db, tarde).aplicar(livre, PARTIDA + timedelta(hours=6))

    assert len(tarde.chamadas) == 1


def test_acima_do_limite_os_pares_que_faltam_usam_o_fator(db, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "traffic_max_consultas_plano", 1)
    livre = _livre(8)

    matriz, resumo = MatrizComTransito(db, GoogleFalso()).aplicar(livre, PARTIDA)

    assert resumo.consultas == 1
    assert resumo.pares_google == PERNAS_POR_CONSULTA
    assert resumo.pares_por_fator == 56 - PERNAS_POR_CONSULTA
    # O fator medido nos 26 pares consultados vale para os outros.
    assert all(
        matriz.duracoes[i][j] == pytest.approx(livre.duracoes[i][j] * 3, rel=0.05, abs=3)
        for i in range(8) for j in range(8) if i != j
    )
    assert any("limite de consultas" in a for a in matriz.avisos)


def test_google_fora_do_ar_levanta_para_o_plano_seguir_sem_transito(db) -> None:
    with pytest.raises(TransitoIndisponivel, match="cota"):
        MatrizComTransito(db, GoogleFalso(falhar=99)).aplicar(_livre(5), PARTIDA)


def test_falha_parcial_e_dita_no_aviso(db) -> None:
    matriz, resumo = MatrizComTransito(db, GoogleFalso(falhar=1)).aplicar(_livre(8), PARTIDA)

    assert resumo.consultas_com_falha == 1
    assert resumo.pares_por_fator > 0
    assert any("falharam" in a for a in matriz.avisos)


def test_dois_pinos_no_mesmo_lugar_nao_viram_consulta(db) -> None:
    livre = _livre(4, repetir_primeiro=True)
    google = GoogleFalso()

    matriz, resumo = MatrizComTransito(db, google).aplicar(livre, PARTIDA)

    assert matriz.duracoes[0][4] == matriz.duracoes[4][0] == 0
    assert resumo.pares_google == 12  # 4 lugares, não 5
    assert all(a != b for pontos, _ in google.chamadas for a, b in pairwise(pontos))


def test_turno_que_ja_comecou_usa_o_transito_de_agora(db) -> None:
    google = GoogleFalso()
    ontem = datetime.now(UTC) - timedelta(days=1)

    _, resumo = MatrizComTransito(db, google).aplicar(_livre(3), ontem)

    assert resumo.partida > ontem + timedelta(hours=23)
    assert db.query(TrafficLeg).count() == 6


# --------------------------------------------------------------------------- #
# O plano
# --------------------------------------------------------------------------- #
ADMIN = "admin@britto.com.br"


@pytest.fixture
def admin(client: TestClient, criar_usuario, autenticar):
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    return autenticar(ADMIN)


@pytest.fixture
def cenario(db):
    base = BaseLocation(
        name="Loja", address="Av. Afonso Pena, 1500", latitude=-20.4697,
        longitude=-54.6201, geocode_status="MANUAL", is_default=True,
    )
    caminhao = Vehicle(name="Caminhao", plate="AAA1A11", crew_size=2)
    db.add_all([base, caminhao])
    for i, (lat, lon) in enumerate([(-20.4550, -54.6100), (-20.4800, -54.6400)]):
        db.add(Delivery(
            address=f"Rua {i}, 100", recipient_name=f"Cliente {i}", latitude=lat,
            longitude=lon, geocode_status="MANUAL", scheduled_date=AMANHA, status="PENDENTE",
        ))
    db.commit()
    return base, caminhao


@pytest.fixture
def google(monkeypatch):
    """Trânsito ligado, com o Google falso: cada perna leva 30 min."""
    falso = GoogleFalso()

    def meia_hora(pontos, partida=None):
        falso.chamadas.append((pontos, partida))
        n = len(pontos) - 1
        return TempoComTransito([1800] * n, [600] * n, [5000] * n)

    monkeypatch.setattr(transito, "disponivel", lambda: True)
    monkeypatch.setattr(transito, "consultar", meia_hora)
    return falso


def _calcular(client, admin, cenario, **extra):
    base, caminhao = cenario
    return client.post("/api/v1/planejamento/calcular", headers=admin, json={
        "date": AMANHA.isoformat(), "base_id": base.id, "vehicle_ids": [caminhao.id],
        "limite_tempo_s": 2, "inicio_turno": "08:00", **extra,
    })


def test_plano_usa_o_transito_e_diz_quanto_ele_pesou(
    client: TestClient, admin, cenario, google
) -> None:
    resposta = _calcular(client, admin, cenario)

    assert resposta.status_code == 201, resposta.text
    plano = resposta.json()
    assert plano["matrix_source"] == "GOOGLE_TRANSITO"
    t = plano["transito"]
    assert t["considerado"] is True
    assert t["consultas"] == len(google.chamadas) == 1  # 3 lugares: 6 pares
    assert t["estrada_transito_s"] == 3 * 1800  # base -> A -> B -> base
    assert t["estrada_livre_s"] < t["estrada_transito_s"]
    # A partida pedida ao Google é 08:00 de Campo Grande.
    assert datetime.fromisoformat(t["partida"]).astimezone(UTC).hour == 12
    entregas = [p for p in plano["routes"][0]["stops"] if p["stop_type"] == "ENTREGA"]
    assert [p["duration_from_previous_s"] for p in entregas] == [1800, 1800]


def test_recalcular_reaproveita_o_que_ja_foi_medido(
    client: TestClient, admin, cenario, google
) -> None:
    _calcular(client, admin, cenario)

    segundo = _calcular(client, admin, cenario).json()

    assert segundo["transito"]["consultas"] == 0
    assert segundo["transito"]["pares_do_cache"] == 6


def test_transito_muda_o_que_cabe_na_janela(
    client: TestClient, admin, cenario, google, db
) -> None:
    """O ponto do trânsito no planejamento: com a rua livre a entrega das
    8h às 8h15 cabe; com 30 min de trânsito, não — e o plano diz isso em vez
    de prometer um horário que o caminhão não cumpre."""
    primeira = db.query(Delivery).filter_by(recipient_name="Cliente 0").one()
    primeira.time_window_start, primeira.time_window_end = time(8, 0), time(8, 15)
    db.commit()

    sem = _calcular(client, admin, cenario, considerar_transito=False).json()
    com = _calcular(client, admin, cenario).json()

    assert sem["unassigned"] == []
    assert [u["rotulo"] for u in com["unassigned"]] == ["Cliente 0"]


def test_calculo_sem_transito_quando_pedido(
    client: TestClient, admin, cenario, google
) -> None:
    plano = _calcular(client, admin, cenario, considerar_transito=False).json()

    assert plano["matrix_source"] == "HAVERSINE"
    assert plano["transito"] == {"considerado": False, "motivo": "desligado neste calculo"}
    assert google.chamadas == []


def test_google_fora_do_ar_nao_impede_o_plano(
    client: TestClient, admin, cenario, monkeypatch
) -> None:
    def fora(pontos, partida=None):
        raise TransitoIndisponivel("o Google respondeu 503")

    monkeypatch.setattr(transito, "disponivel", lambda: True)
    monkeypatch.setattr(transito, "consultar", fora)

    plano = _calcular(client, admin, cenario).json()

    assert plano["matrix_source"] == "HAVERSINE"
    assert plano["transito"]["considerado"] is False
    assert any("transito nao foi considerado" in a for a in plano["avisos"])


def test_sem_transito_configurado_o_plano_diz_que_e_rua_livre(
    client: TestClient, admin, cenario
) -> None:
    plano = _calcular(client, admin, cenario).json()

    assert plano["transito"] == {"considerado": False, "motivo": "transito nao configurado"}
    opcoes = client.get("/api/v1/planejamento/opcoes", headers=admin).json()
    assert opcoes["transito_disponivel"] is False
