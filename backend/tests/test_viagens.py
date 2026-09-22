"""Mais de uma viagem por dia: o caminhão volta à base, recarrega e sai de novo.

A regra que estes testes protegem: **carga que ainda está na base não está no
caminhão**. As entregas da segunda viagem só entram em rota quando o motorista
diz que recarregou — até lá, o painel não pode mostrá-las como se estivessem
com ele.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from app.core.enums import Role
from app.models.base_location import BaseLocation
from app.models.delivery import Delivery
from app.models.driver import Driver
from app.models.vehicle import Vehicle
from app.optimization import (
    Demanda,
    OpcoesOtimizacao,
    OptimizationRequest,
    OrToolsEngine,
    ParadaPlanejada,
    VeiculoDisponivel,
)
from app.routing.base import Ponto
from app.routing.haversine import HaversineProvider

ADMIN = "admin@britto.com.br"
MOTORISTA = "carlos@britto.com.br"
HOJE = date.today()

BASE = (-20.4697, -54.6201)
PONTOS = [
    (-20.4550, -54.6100),
    (-20.4800, -54.6400),
    (-20.4600, -54.6600),
    (-20.4900, -54.6000),
    (-20.4700, -54.6300),
    (-20.4450, -54.6200),
]
RECARGA_S = 1800


# --------------------------------------------------------------------------- #
# Motor: a viagem 2 só existe quando precisa, e só depois da recarga
# --------------------------------------------------------------------------- #
def _pedido(*, max_viagens: int, peso: float = 300, jornada_s: int = 8 * 3600):
    pontos = [Ponto("base", *BASE), *[Ponto(f"p{i}", *p) for i, p in enumerate(PONTOS)]]
    matriz = HaversineProvider().matriz(pontos)
    return OptimizationRequest(
        deposito=ParadaPlanejada("base", *BASE, "Base", 0),
        paradas=[
            ParadaPlanejada(f"p{i}", *p, f"P{i}", 1800, Demanda(peso_kg=peso))
            for i, p in enumerate(PONTOS)
        ],
        veiculos=[
            VeiculoDisponivel(
                "v1", "Caminhao", capacidade_peso_kg=1000, jornada_s=jornada_s
            )
        ],
        duracoes=matriz.duracoes,
        distancias=matriz.distancias,
        opcoes=OpcoesOtimizacao(
            limite_tempo_s=2, max_viagens=max_viagens, recarga_s=RECARGA_S
        ),
    )


def test_uma_viagem_so_deixa_de_fora_o_que_nao_cabe() -> None:
    """1.800 kg de entregas num caminhão de 1.000 kg: metade fica."""
    resultado = OrToolsEngine().resolver(_pedido(max_viagens=1))

    assert len(resultado.dispensadas) == 3
    assert resultado.rotas[0].quantidade_viagens == 1


def test_com_duas_viagens_a_mesma_carga_cabe_no_mesmo_caminhao() -> None:
    resultado = OrToolsEngine().resolver(_pedido(max_viagens=2))

    assert resultado.dispensadas == []
    rota = resultado.rotas[0]
    assert rota.quantidade_viagens == 2
    assert {p.viagem for p in rota.paradas} == {1, 2}
    # A segunda viagem sai só depois de voltar e recarregar.
    recarga = rota.recargas[0]
    assert recarga.saida_s == recarga.chegada_s + RECARGA_S
    assert min(p.chegada_estimada_s for p in rota.paradas if p.viagem == 2) > recarga.saida_s
    # E a recarga entra na duração do dia.
    assert rota.duracao_total_s >= RECARGA_S


def test_viagem_que_nao_precisa_nao_acontece() -> None:
    """Carga leve com três viagens liberadas: o caminhão sai uma vez só."""
    resultado = OrToolsEngine().resolver(_pedido(max_viagens=3, peso=100))

    assert resultado.dispensadas == []
    assert resultado.rotas[0].quantidade_viagens == 1
    assert resultado.rotas[0].recargas == []


def test_a_jornada_vale_para_o_dia_inteiro_nao_por_viagem() -> None:
    """Numa jornada de 3 h não cabe a segunda viagem — e o sistema diz isso
    deixando entregas de fora, em vez de prometer um dia que não existe."""
    resultado = OrToolsEngine().resolver(_pedido(max_viagens=3, jornada_s=3 * 3600))

    assert resultado.dispensadas != []
    rota = resultado.rotas[0]
    assert rota.quantidade_viagens == 1
    assert rota.chegada_base_s <= 3 * 3600


# --------------------------------------------------------------------------- #
# Plano
# --------------------------------------------------------------------------- #
@pytest.fixture
def cenario(client: TestClient, criar_usuario, autenticar, db):
    """Base, um caminhão de 1.000 kg e 1.800 kg de entregas."""
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    usuario_motorista = criar_usuario(email=MOTORISTA, role=Role.MOTORISTA, name="Carlos")

    base = BaseLocation(
        name="Loja", address="Av. Afonso Pena, 1500", latitude=BASE[0], longitude=BASE[1],
        geocode_status="MANUAL", is_default=True,
    )
    veiculo = Vehicle(name="Caminhao", plate="AAA1A11", capacity_weight_kg=1000)
    motorista = Driver(name="Carlos", user_id=usuario_motorista.id)
    db.add_all([base, veiculo, motorista])
    for i, (lat, lon) in enumerate(PONTOS):
        db.add(Delivery(
            address=f"Rua {i}, 100", recipient_name=f"Cliente {i}", latitude=lat,
            longitude=lon, geocode_status="MANUAL", scheduled_date=HOJE,
            status="PENDENTE", weight_kg=300,
        ))
    db.commit()
    return {
        "admin": autenticar(ADMIN),
        "motorista": autenticar(MOTORISTA),
        "base": base,
        "veiculo": veiculo,
        "driver": motorista,
    }


def _calcular(client, cenario, **extra):
    return client.post("/api/v1/planejamento/calcular", headers=cenario["admin"], json={
        "date": HOJE.isoformat(),
        "base_id": cenario["base"].id,
        "vehicle_ids": [cenario["veiculo"].id],
        "driver_ids": [cenario["driver"].id],
        "limite_tempo_s": 2,
        "inicio_turno": "08:00",
        **extra,
    })


def test_plano_grava_a_volta_a_base_como_parada(client: TestClient, cenario) -> None:
    plano = _calcular(client, cenario, max_viagens=2, recarga_min=30).json()

    paradas = plano["routes"][0]["stops"]
    tipos = [p["stop_type"] for p in paradas]
    assert tipos[0] == "BASE_SAIDA"
    assert tipos[-1] == "BASE_RETORNO"
    assert tipos.count("BASE_RECARGA") == 1
    recarga = next(p for p in paradas if p["stop_type"] == "BASE_RECARGA")
    assert recarga["service_time_s"] == 30 * 60
    assert recarga["address"] == "Av. Afonso Pena, 1500"
    # Viagem 1 antes da recarga, viagem 2 depois — e a sequência não se repete.
    assert [p["sequence"] for p in paradas] == sorted(p["sequence"] for p in paradas)
    antes = [p for p in paradas if p["sequence"] < recarga["sequence"]]
    depois = [p for p in paradas if p["sequence"] > recarga["sequence"]]
    assert {p["trip_number"] for p in antes} == {1}
    assert {p["trip_number"] for p in depois} == {2}


def test_horarios_previstos_incluem_o_tempo_da_recarga(client: TestClient, cenario) -> None:
    plano = _calcular(client, cenario, max_viagens=2, recarga_min=45).json()

    paradas = sorted(plano["routes"][0]["stops"], key=lambda p: p["sequence"])
    quando = {p["sequence"]: datetime.fromisoformat(p["estimated_arrival"]) for p in paradas}
    recarga = next(p for p in paradas if p["stop_type"] == "BASE_RECARGA")
    primeira_da_viagem_2 = next(p for p in paradas if p["sequence"] > recarga["sequence"])

    espera = quando[primeira_da_viagem_2["sequence"]] - quando[recarga["sequence"]]
    assert espera.total_seconds() >= 45 * 60
    # Toda parada tem hora prevista, inclusive a volta final.
    assert all(p["estimated_arrival"] for p in paradas)


def test_sem_pedir_viagem_extra_o_plano_continua_de_uma_viagem_so(
    client: TestClient, cenario
) -> None:
    plano = _calcular(client, cenario).json()

    paradas = plano["routes"][0]["stops"]
    assert [p["stop_type"] for p in paradas].count("BASE_RECARGA") == 0
    assert len(plano["unassigned"]) == 3


# --------------------------------------------------------------------------- #
# Motorista
# --------------------------------------------------------------------------- #
@pytest.fixture
def rota(client: TestClient, cenario):
    """Rota de duas viagens, confirmada e pronta para o motorista."""
    plano = _calcular(client, cenario, max_viagens=2, recarga_min=30).json()
    client.post(
        f"/api/v1/planejamento/{plano['id']}/confirmar", headers=cenario["admin"], json={}
    )
    return client.get("/api/v1/motorista/rotas", headers=cenario["motorista"]).json()[0]


def _recarregar(client, cenario, rota_id):
    return client.get(f"/api/v1/motorista/rotas/{rota_id}", headers=cenario["motorista"]).json()


def _paradas(rota, viagem=None, tipo="ENTREGA"):
    return [
        p
        for p in sorted(rota["stops"], key=lambda p: p["sequence"])
        if p["stop_type"] == tipo and (viagem is None or p["trip_number"] == viagem)
    ]


def _recarga(rota):
    return next(p for p in rota["stops"] if p["stop_type"] == "BASE_RECARGA")


def test_iniciar_leva_so_a_carga_da_primeira_viagem(
    client: TestClient, cenario, rota
) -> None:
    """O caminhão saiu com a carga da viagem 1. A da viagem 2 continua na base
    — e o sistema não pode dizer que está a caminho."""
    client.post(f"/api/v1/motorista/rotas/{rota['id']}/iniciar", headers=cenario["motorista"])

    atual = _recarregar(client, cenario, rota["id"])
    viagem1 = [i["status"] for p in _paradas(atual, 1) for i in p["items"]]
    viagem2 = [i["status"] for p in _paradas(atual, 2) for i in p["items"]]

    assert viagem1 and set(viagem1) == {"EM_ROTA"}
    assert viagem2 and set(viagem2) == {"PLANEJADA"}


def test_entrega_da_proxima_viagem_nao_se_registra_antes_da_recarga(
    client: TestClient, cenario, rota
) -> None:
    client.post(f"/api/v1/motorista/rotas/{rota['id']}/iniciar", headers=cenario["motorista"])
    atual = _recarregar(client, cenario, rota["id"])
    parada = _paradas(atual, 2)[0]

    resposta = client.post(
        f"/api/v1/motorista/paradas/{parada['id']}/cheguei",
        headers=cenario["motorista"],
        json={},
    )

    assert resposta.status_code == 422
    assert "viagem 2" in resposta.json()["mensagem"]


def test_recarga_exige_chegada_na_base(client: TestClient, cenario, rota) -> None:
    client.post(f"/api/v1/motorista/rotas/{rota['id']}/iniciar", headers=cenario["motorista"])

    resposta = client.post(
        f"/api/v1/motorista/paradas/{_recarga(rota)['id']}/recarga",
        headers=cenario["motorista"],
    )

    assert resposta.status_code == 422
    assert "chegada" in resposta.json()["mensagem"]


def test_recarga_exige_as_entregas_da_viagem_anterior_registradas(
    client: TestClient, cenario, rota
) -> None:
    """O caminhão está na base com a entrega que voltou. Ela precisa ser dita
    "não entregue", com motivo — não sumir na recarga."""
    client.post(f"/api/v1/motorista/rotas/{rota['id']}/iniciar", headers=cenario["motorista"])
    client.post(
        f"/api/v1/motorista/paradas/{_recarga(rota)['id']}/cheguei",
        headers=cenario["motorista"],
        json={},
    )

    resposta = client.post(
        f"/api/v1/motorista/paradas/{_recarga(rota)['id']}/recarga",
        headers=cenario["motorista"],
    )

    assert resposta.status_code == 422
    assert "sem registro" in resposta.json()["mensagem"]


def test_fluxo_das_duas_viagens(client: TestClient, cenario, rota) -> None:
    motorista = cenario["motorista"]
    client.post(f"/api/v1/motorista/rotas/{rota['id']}/iniciar", headers=motorista)

    atual = _recarregar(client, cenario, rota["id"])
    for parada in _paradas(atual, 1):
        client.post(
            f"/api/v1/motorista/paradas/{parada['id']}/cheguei", headers=motorista, json={}
        )
        for item in parada["items"]:
            client.post(
                f"/api/v1/motorista/entregas/{item['id']}/entregue",
                headers=motorista,
                json={"recebedor": "Portaria"},
            )

    recarga = _recarga(atual)
    client.post(
        f"/api/v1/motorista/paradas/{recarga['id']}/cheguei", headers=motorista, json={}
    )
    resposta = client.post(
        f"/api/v1/motorista/paradas/{recarga['id']}/recarga", headers=motorista
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["status"] == "CONCLUIDA"
    assert resposta.json()["departed_at"] is not None

    depois = _recarregar(client, cenario, rota["id"])
    assert {i["status"] for p in _paradas(depois, 2) for i in p["items"]} == {"EM_ROTA"}

    # E agora a entrega da viagem 2 pode ser registrada.
    parada = _paradas(depois, 2)[0]
    assert (
        client.post(
            f"/api/v1/motorista/paradas/{parada['id']}/cheguei", headers=motorista, json={}
        ).status_code
        == 200
    )


def test_recarga_de_outro_motorista_nao_e_acessivel(
    client: TestClient, cenario, rota, criar_usuario, autenticar
) -> None:
    criar_usuario(email="outro@britto.com.br", role=Role.MOTORISTA)

    resposta = client.post(
        f"/api/v1/motorista/paradas/{_recarga(rota)['id']}/recarga",
        headers=autenticar("outro@britto.com.br"),
    )

    assert resposta.status_code == 404
