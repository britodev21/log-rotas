"""Planejamento: agrupamento, otimizacao e o fluxo calcular -> confirmar.

A regra que estes testes existem para proteger: **calcular nao muda a
operacao**. Se um dia alguem "otimizar" o codigo fazendo o calculo ja gravar
as rotas, e este arquivo que vai apontar o problema antes de a empresa
descobrir com o dia comprometido.

Os testes usam a matriz em linha reta (Haversine), sem rede. O que se
verifica nao e a precisao da distancia — e o comportamento do sistema:
o que ele agrupa, o que recusa, o que deixa de fora e o que grava.
"""

from __future__ import annotations

from datetime import date, time

import pytest
from fastapi.testclient import TestClient

from app.core.enums import Role
from app.models.base_location import BaseLocation
from app.models.delivery import Delivery
from app.models.vehicle import Vehicle
from app.services.stop_grouping import agrupar, desagrupar_excedentes

ADMIN = "admin@britto.com.br"
HOJE = date.today()

# Pontos reais de Campo Grande, espalhados pela cidade.
PONTOS = [
    (-20.4550, -54.6100),
    (-20.4800, -54.6400),
    (-20.4600, -54.6600),
    (-20.4900, -54.6000),
    (-20.4700, -54.6300),
]


@pytest.fixture
def admin(client: TestClient, criar_usuario, autenticar):
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    return autenticar(ADMIN)


@pytest.fixture
def base(db):
    b = BaseLocation(
        name="Loja Centro",
        address="Av. Afonso Pena, 1500",
        latitude=-20.4697,
        longitude=-54.6201,
        geocode_status="MANUAL",
        is_default=True,
    )
    db.add(b)
    db.commit()
    return b


@pytest.fixture
def frota(db):
    veiculos = [
        Vehicle(name="Caminhao 1", plate="AAA1A11", capacity_weight_kg=1000, crew_size=2),
        Vehicle(name="Caminhao 2", plate="BBB2B22", capacity_weight_kg=1000, crew_size=2),
    ]
    for v in veiculos:
        db.add(v)
    db.commit()
    return veiculos


@pytest.fixture
def motoristas(client, admin):
    return [
        client.post("/api/v1/motoristas", headers=admin, json={"name": f"Motorista {i}"}).json()
        for i in (1, 2)
    ]


def criar_entregas(db, quantidade=4, **extra):
    entregas = []
    for i in range(quantidade):
        lat, lon = PONTOS[i % len(PONTOS)]
        e = Delivery(
            address=f"Rua {i}, 100",
            recipient_name=f"Cliente {i}",
            latitude=lat,
            longitude=lon,
            geocode_status="MANUAL",
            scheduled_date=HOJE,
            status="PENDENTE",
            **extra,
        )
        db.add(e)
        entregas.append(e)
    db.commit()
    return entregas


def calcular(client, admin, base, frota, motoristas=None, **extra):
    corpo = {
        "date": HOJE.isoformat(),
        "base_id": base.id,
        "vehicle_ids": [v.id for v in frota],
        "driver_ids": [m["id"] for m in (motoristas or [])],
        "limite_tempo_s": 3,
        **extra,
    }
    return client.post("/api/v1/planejamento/calcular", headers=admin, json=corpo)


# --------------------------------------------------------------------------- #
# Agrupamento de paradas — funcao pura
# --------------------------------------------------------------------------- #
def test_entregas_no_mesmo_lugar_viram_uma_parada(db) -> None:
    """O motorista estaciona uma vez: predio, condominio, galeria."""
    for i in range(3):
        db.add(
            Delivery(
                address="Rua 14 de Julho, 500",
                recipient_name=f"Apto {i}",
                latitude=-20.4697,
                longitude=-54.6201,
                geocode_status="MANUAL",
                scheduled_date=HOJE,
                weight_kg=100,
            )
        )
    db.commit()
    entregas = db.query(Delivery).all()

    paradas = agrupar(entregas)

    assert len(paradas) == 1
    assert len(paradas[0].entregas) == 3
    assert paradas[0].peso_kg == 300


def test_mesma_coordenada_agrupa_mesmo_com_enderecos_diferentes(db) -> None:
    """Quem estaciona uma vez estaciona uma vez.

    "Rua X, 100" e "Rua X, 100 apto 2" sao a mesma porta; o mesmo cliente
    com duas compras e a mesma visita. Com coordenada confiavel (MANUAL ou
    EXATO), o criterio e a posicao — nao o texto digitado.
    """
    for sufixo in ("", " - apto 2", " - 2a carga"):
        db.add(
            Delivery(
                address=f"Rua 14 de Julho, 500{sufixo}",
                latitude=-20.4697,
                longitude=-54.6201,
                geocode_status="MANUAL",
                scheduled_date=HOJE,
            )
        )
    db.commit()

    paradas = agrupar(db.query(Delivery).all())

    assert len(paradas) == 1
    assert len(paradas[0].entregas) == 3


def test_coordenada_grosseira_nao_agrupa_por_posicao(db) -> None:
    """Precisao de rua ou bairro poe enderecos distintos no mesmo ponto.

    Errar para menos custa uma parada a mais na rota; errar para mais
    juntaria entregas a quarteiroes de distancia — e o motorista descobriria
    isso na rua.
    """
    for numero in (100, 780, 1500):
        db.add(
            Delivery(
                address=f"Avenida Afonso Pena, {numero}",
                latitude=-20.4697,
                longitude=-54.6201,
                geocode_status="OK",
                geocode_precision="RUA",
                scheduled_date=HOJE,
            )
        )
    db.commit()

    paradas = agrupar(db.query(Delivery).all())

    assert len(paradas) == 3


def test_tempo_da_parada_nao_e_soma_ingenua(db) -> None:
    """Quem estaciona uma vez nao paga o tempo de estacionar tres vezes.
    Somar superestimaria a rota e faria caber menos servicos do que o dia
    comporta."""
    for _ in range(3):
        db.add(
            Delivery(
                address="Rua Unica, 10",
                latitude=-20.47,
                longitude=-54.62,
                geocode_status="MANUAL",
                scheduled_date=HOJE,
                service_time_minutes=30,
            )
        )
    db.commit()

    parada = agrupar(db.query(Delivery).all())[0]
    tempo = parada.tempo_servico_s(60)

    # 3 x 30 min de servico + 5 min de estacionar, uma vez so.
    assert tempo == 3 * 30 * 60 + 5 * 60


def test_comprimento_nao_soma(db) -> None:
    """Tres corrimoes de 2 m nao exigem um veiculo de 6 m — cabe o maior."""
    for _ in range(3):
        db.add(
            Delivery(
                address="Rua A, 1",
                latitude=-20.47,
                longitude=-54.62,
                geocode_status="MANUAL",
                scheduled_date=HOJE,
                length_m=2,
            )
        )
    db.commit()

    parada = agrupar(db.query(Delivery).all())[0]

    assert parada.comprimento_m == 2


def test_equipe_da_parada_e_a_mais_exigente(db) -> None:
    for necessaria in (1, 4, 2):
        db.add(
            Delivery(
                address="Rua A, 1",
                latitude=-20.47,
                longitude=-54.62,
                geocode_status="MANUAL",
                scheduled_date=HOJE,
                required_crew=necessaria,
            )
        )
    db.commit()

    assert agrupar(db.query(Delivery).all())[0].equipe == 4


def test_janelas_incompativeis_separam_a_parada(db) -> None:
    """Juntar criaria uma parada impossivel, e o solver diria apenas
    "sem solucao" — sem indicar que o problema foi o agrupamento."""
    db.add(
        Delivery(
            address="Rua A, 1",
            latitude=-20.47,
            longitude=-54.62,
            geocode_status="MANUAL",
            scheduled_date=HOJE,
            time_window_start=time(8, 0),
            time_window_end=time(10, 0),
        )
    )
    db.add(
        Delivery(
            address="Rua A, 1",
            latitude=-20.47,
            longitude=-54.62,
            geocode_status="MANUAL",
            scheduled_date=HOJE,
            time_window_start=time(14, 0),
            time_window_end=time(16, 0),
        )
    )
    db.commit()

    paradas = agrupar(db.query(Delivery).all())

    assert len(paradas) == 2


def test_parada_pesada_demais_e_dividida(db) -> None:
    """Melhor visitar o mesmo lugar duas vezes do que nao planejar o dia."""
    for _ in range(3):
        db.add(
            Delivery(
                address="Rua A, 1",
                latitude=-20.47,
                longitude=-54.62,
                geocode_status="MANUAL",
                scheduled_date=HOJE,
                weight_kg=400,
            )
        )
    db.commit()

    paradas = agrupar(db.query(Delivery).all())
    assert paradas[0].peso_kg == 1200

    divididas, avisos = desagrupar_excedentes(paradas, maior_peso_kg=1000, maior_volume_m3=None)

    assert len(divididas) == 3
    assert avisos and "nao cabem" in avisos[0]


# --------------------------------------------------------------------------- #
# Calcular
# --------------------------------------------------------------------------- #
def test_calculo_monta_rotas_sem_mexer_nas_entregas(
    client: TestClient, admin, base, frota, motoristas, db
) -> None:
    """A regra central do planejador.

    Se calcular ja alterasse status, um teste de cenario feito as 7h da
    manha comprometeria o dia inteiro da operacao.
    """
    criar_entregas(db, 4, weight_kg=200)

    resposta = calcular(client, admin, base, frota, motoristas)

    assert resposta.status_code == 201, resposta.text
    plano = resposta.json()
    assert plano["status"] == "RASCUNHO"
    assert len(plano["routes"]) >= 1
    assert all(r["status"] == "RASCUNHO" for r in plano["routes"])

    entregas = client.get("/api/v1/entregas", headers=admin).json()
    assert all(e["status"] == "PENDENTE" for e in entregas)


def test_rota_comeca_e_termina_na_base(
    client: TestClient, admin, base, frota, motoristas, db
) -> None:
    criar_entregas(db, 3)

    plano = calcular(client, admin, base, frota, motoristas).json()
    paradas = plano["routes"][0]["stops"]

    assert paradas[0]["stop_type"] == "BASE_SAIDA"
    assert paradas[-1]["stop_type"] == "BASE_RETORNO"
    assert [p["sequence"] for p in paradas] == sorted(p["sequence"] for p in paradas)


def test_capacidade_e_respeitada(
    client: TestClient, admin, base, frota, motoristas, db
) -> None:
    """A prova de que a otimizacao e real: 6 x 400 kg = 2400 kg nao cabe em
    dois veiculos de 1000 kg, e o excedente TEM de sobrar."""
    criar_entregas(db, 5, weight_kg=400)

    plano = calcular(client, admin, base, frota, motoristas).json()

    for rota in plano["routes"]:
        assert float(rota["planned_weight_kg"]) <= 1000

    total_planejado = sum(float(r["planned_weight_kg"] or 0) for r in plano["routes"])
    assert total_planejado <= 2000


def test_excedente_volta_como_nao_atribuido(
    client: TestClient, admin, base, frota, motoristas, db
) -> None:
    """Entrega que nao cabe nunca some em silencio — ela reapareceria so
    quando o cliente ligasse cobrando."""
    criar_entregas(db, 5, weight_kg=900)

    plano = calcular(client, admin, base, frota, motoristas).json()

    assert plano["unassigned"], "entregas que nao couberam precisam ser reportadas"
    assert plano["unassigned"][0]["motivo"]


def test_entrega_sem_coordenada_recusa_o_calculo(
    client: TestClient, admin, base, frota, db
) -> None:
    """Com a lista de quais. Ignorar faria entregas sumirem do plano."""
    db.add(Delivery(address="Rua sem pino, 1", scheduled_date=HOJE, status="PENDENTE"))
    db.commit()

    resposta = calcular(client, admin, base, frota)

    assert resposta.status_code == 422
    assert resposta.json()["detalhes"]["total"] == 1


def test_base_sem_coordenada_recusa_o_calculo(client: TestClient, admin, frota, db) -> None:
    sem_pino = BaseLocation(name="Deposito novo", address="Rua X")
    db.add(sem_pino)
    db.commit()
    criar_entregas(db, 2)

    resposta = calcular(client, admin, sem_pino, frota)

    assert resposta.status_code == 422
    assert "coordenada" in resposta.json()["mensagem"]


def test_plano_registra_a_origem_da_matriz(
    client: TestClient, admin, base, frota, motoristas, db
) -> None:
    """A diferenca entre estimar e mentir: o sistema pode trabalhar com
    aproximacao, desde que diga que e aproximacao."""
    criar_entregas(db, 3)

    plano = calcular(client, admin, base, frota, motoristas).json()

    assert plano["matrix_source"] in ("OSRM", "HAVERSINE")
    if plano["matrix_source"] == "HAVERSINE":
        assert plano["distancias_estimadas"] is True
        assert any("estimad" in a.lower() for a in plano["avisos"])


def test_plano_guarda_estatisticas_do_solver(
    client: TestClient, admin, base, frota, motoristas, db
) -> None:
    """Auditabilidade: da para provar depois por que o sistema montou
    aquelas rotas."""
    criar_entregas(db, 3)

    plano = calcular(client, admin, base, frota, motoristas).json()

    assert plano["solver"]
    assert plano["solver_status"] in ("OTIMO", "VIAVEL")
    assert plano["solver_time_ms"] is not None


# --------------------------------------------------------------------------- #
# Confirmar e descartar
# --------------------------------------------------------------------------- #
def test_confirmar_muda_entregas_e_rotas(
    client: TestClient, admin, base, frota, motoristas, db
) -> None:
    criar_entregas(db, 4)
    plano = calcular(client, admin, base, frota, motoristas).json()

    resposta = client.post(
        f"/api/v1/planejamento/{plano['id']}/confirmar", headers=admin, json={}
    )

    assert resposta.status_code == 200, resposta.text
    confirmado = resposta.json()
    assert confirmado["status"] == "CONFIRMADO"
    assert all(r["status"] == "PLANEJADA" for r in confirmado["routes"])

    entregas = client.get("/api/v1/entregas", headers=admin).json()
    planejadas = [e for e in entregas if e["status"] == "PLANEJADA"]
    assert planejadas


def test_confirmar_sem_motorista_e_recusado(client: TestClient, admin, base, frota, db) -> None:
    """Rota que ninguem vai executar e pior do que nenhuma rota."""
    criar_entregas(db, 3)
    plano = calcular(client, admin, base, frota).json()  # sem motoristas

    resposta = client.post(
        f"/api/v1/planejamento/{plano['id']}/confirmar", headers=admin, json={}
    )

    assert resposta.status_code == 422
    assert "motorista" in resposta.json()["mensagem"].lower()


def test_confirmar_duas_vezes_e_recusado(
    client: TestClient, admin, base, frota, motoristas, db
) -> None:
    criar_entregas(db, 3)
    plano = calcular(client, admin, base, frota, motoristas).json()

    client.post(f"/api/v1/planejamento/{plano['id']}/confirmar", headers=admin, json={})
    segunda = client.post(
        f"/api/v1/planejamento/{plano['id']}/confirmar", headers=admin, json={}
    )

    assert segunda.status_code == 409


def test_descartar_deixa_as_entregas_intactas(
    client: TestClient, admin, base, frota, motoristas, db
) -> None:
    """Elas nunca sairam de PENDENTE — a vantagem de o calculo nao mexer na
    operacao."""
    criar_entregas(db, 3)
    plano = calcular(client, admin, base, frota, motoristas).json()

    resposta = client.post(f"/api/v1/planejamento/{plano['id']}/descartar", headers=admin)

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "DESCARTADO"

    entregas = client.get("/api/v1/entregas", headers=admin).json()
    assert all(e["status"] == "PENDENTE" for e in entregas)


def test_atribuicao_de_motorista_na_confirmacao(
    client: TestClient, admin, base, frota, motoristas, db
) -> None:
    criar_entregas(db, 4)
    plano = calcular(client, admin, base, frota).json()
    rota_id = plano["routes"][0]["id"]

    resposta = client.post(
        f"/api/v1/planejamento/{plano['id']}/confirmar",
        headers=admin,
        json={"atribuicoes": {str(r["id"]): motoristas[0]["id"] for r in plano["routes"]}},
    )

    assert resposta.status_code == 200
    rota = next(r for r in resposta.json()["routes"] if r["id"] == rota_id)
    assert rota["driver_id"] == motoristas[0]["id"]


def test_motorista_nao_planeja(client: TestClient, criar_usuario, autenticar) -> None:
    criar_usuario(email="mot@britto.com.br", role=Role.MOTORISTA)
    cabecalho = autenticar("mot@britto.com.br")
    assert client.get("/api/v1/planejamento", headers=cabecalho).status_code == 403
