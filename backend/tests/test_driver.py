"""Execucao da rota pelo motorista.

Duas coisas sao testadas aqui, e as duas doem quando falham:

1. **Isolamento.** O motorista nao pode ver nem tocar a rota de um colega.
   Falha aqui e vazamento de dado operacional e entrega marcada por quem
   nao fez.
2. **Integridade do que aconteceu de verdade.** Entrega sem registro nao
   pode virar "entregue" por omissao — isso esconderia servico nao feito, e
   a empresa so descobriria quando o cliente ligasse.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.enums import Role
from app.models.base_location import BaseLocation
from app.models.delivery import Delivery
from app.models.driver import Driver
from app.models.vehicle import Vehicle

ADMIN = "admin@britto.com.br"
MOTORISTA = "carlos@britto.com.br"
OUTRO_MOTORISTA = "joana@britto.com.br"
HOJE = date.today()

PONTOS = [(-20.4550, -54.6100), (-20.4800, -54.6400), (-20.4600, -54.6600)]


@pytest.fixture
def cenario(client: TestClient, criar_usuario, autenticar, db):
    """Uma rota confirmada, pronta para ser executada."""
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    cabecalho_admin = autenticar(ADMIN)

    usuario_motorista = criar_usuario(email=MOTORISTA, role=Role.MOTORISTA, name="Carlos")

    base = BaseLocation(
        name="Loja",
        latitude=-20.4697,
        longitude=-54.6201,
        geocode_status="MANUAL",
        is_default=True,
    )
    veiculo = Vehicle(name="Caminhao", plate="AAA1A11", capacity_weight_kg=2000)
    motorista = Driver(name="Carlos", user_id=usuario_motorista.id)
    db.add_all([base, veiculo, motorista])
    db.commit()

    for i, (lat, lon) in enumerate(PONTOS):
        db.add(
            Delivery(
                address=f"Rua {i}, 100",
                recipient_name=f"Cliente {i}",
                latitude=lat,
                longitude=lon,
                geocode_status="MANUAL",
                scheduled_date=HOJE,
                status="PENDENTE",
                weight_kg=100,
            )
        )
    db.commit()

    plano = client.post(
        "/api/v1/planejamento/calcular",
        headers=cabecalho_admin,
        json={
            "date": HOJE.isoformat(),
            "base_id": base.id,
            "vehicle_ids": [veiculo.id],
            "driver_ids": [motorista.id],
            "limite_tempo_s": 3,
        },
    ).json()

    client.post(
        f"/api/v1/planejamento/{plano['id']}/confirmar", headers=cabecalho_admin, json={}
    )

    return {
        "admin": cabecalho_admin,
        "motorista": autenticar(MOTORISTA),
        "plano": plano,
        "base": base,
        "veiculo": veiculo,
        "driver": motorista,
    }


def rota_atual(client, cenario):
    rotas = client.get("/api/v1/motorista/rotas", headers=cenario["motorista"]).json()
    assert rotas, "o motorista deveria ter uma rota confirmada"
    return rotas[0]


def entregas_da_rota(rota):
    return [item for parada in rota["stops"] for item in parada["items"]]


# --------------------------------------------------------------------------- #
# Isolamento
# --------------------------------------------------------------------------- #
def test_motorista_ve_a_propria_rota(client: TestClient, cenario) -> None:
    rota = rota_atual(client, cenario)

    assert rota["status"] == "PLANEJADA"
    assert rota["progresso"]["total"] == len(PONTOS)
    assert rota["progresso"]["concluidas"] == 0


def test_rota_de_outro_motorista_responde_404(
    client: TestClient, cenario, criar_usuario, autenticar, db
) -> None:
    """404, nao 403: dizer "existe mas nao e sua" confirmaria a existencia
    de rotas alheias a quem estivesse sondando."""
    outro_usuario = criar_usuario(email=OUTRO_MOTORISTA, role=Role.MOTORISTA)
    db.add(Driver(name="Joana", user_id=outro_usuario.id))
    db.commit()

    rota = rota_atual(client, cenario)
    resposta = client.get(
        f"/api/v1/motorista/rotas/{rota['id']}", headers=autenticar(OUTRO_MOTORISTA)
    )

    assert resposta.status_code == 404


def test_motorista_sem_cadastro_vinculado_recebe_explicacao(
    client: TestClient, criar_usuario, autenticar
) -> None:
    criar_usuario(email="solto@britto.com.br", role=Role.MOTORISTA)

    resposta = client.get("/api/v1/motorista/rotas", headers=autenticar("solto@britto.com.br"))

    assert resposta.status_code == 404
    assert "vinculado" in resposta.json()["mensagem"]


def test_admin_nao_usa_as_rotas_do_motorista(client: TestClient, cenario) -> None:
    assert client.get("/api/v1/motorista/rotas", headers=cenario["admin"]).status_code == 403


def test_rascunho_nao_aparece_para_o_motorista(client: TestClient, cenario, db) -> None:
    """Mostrar rascunho faria o motorista sair para uma rota que o
    administrador ainda esta revisando."""
    db.add(
        Delivery(
            address="Rua nova, 1",
            latitude=-20.47,
            longitude=-54.63,
            geocode_status="MANUAL",
            scheduled_date=HOJE,
            status="PENDENTE",
        )
    )
    db.commit()

    client.post(
        "/api/v1/planejamento/calcular",
        headers=cenario["admin"],
        json={
            "date": HOJE.isoformat(),
            "base_id": cenario["base"].id,
            "vehicle_ids": [cenario["veiculo"].id],
            "driver_ids": [cenario["driver"].id],
            "limite_tempo_s": 3,
        },
    )

    rotas = client.get("/api/v1/motorista/rotas", headers=cenario["motorista"]).json()

    assert all(r["status"] != "RASCUNHO" for r in rotas)
    assert len(rotas) == 1


# --------------------------------------------------------------------------- #
# Fluxo de execucao
# --------------------------------------------------------------------------- #
def test_iniciar_rota_poe_as_entregas_em_rota(client: TestClient, cenario) -> None:
    rota = rota_atual(client, cenario)

    resposta = client.post(
        f"/api/v1/motorista/rotas/{rota['id']}/iniciar", headers=cenario["motorista"]
    )

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "INICIADA"
    assert resposta.json()["started_at"]

    entregas = client.get("/api/v1/entregas", headers=cenario["admin"]).json()
    assert all(e["status"] == "EM_ROTA" for e in entregas)


def test_nao_pode_ter_duas_rotas_em_andamento(client: TestClient, cenario, db) -> None:
    """O banco tambem impede, por indice parcial. A checagem existe para a
    mensagem ser util em vez de um erro de constraint."""
    rota = rota_atual(client, cenario)
    client.post(f"/api/v1/motorista/rotas/{rota['id']}/iniciar", headers=cenario["motorista"])

    # Segunda rota, mesma pessoa.
    db.add(
        Delivery(
            address="Rua outra, 1",
            latitude=-20.46,
            longitude=-54.64,
            geocode_status="MANUAL",
            scheduled_date=HOJE,
            status="PENDENTE",
        )
    )
    db.commit()
    plano = client.post(
        "/api/v1/planejamento/calcular",
        headers=cenario["admin"],
        json={
            "date": HOJE.isoformat(),
            "base_id": cenario["base"].id,
            "vehicle_ids": [cenario["veiculo"].id],
            "driver_ids": [cenario["driver"].id],
            "limite_tempo_s": 3,
        },
    ).json()
    client.post(
        f"/api/v1/planejamento/{plano['id']}/confirmar", headers=cenario["admin"], json={}
    )

    segunda = client.get("/api/v1/motorista/rotas", headers=cenario["motorista"]).json()
    nova = next(r for r in segunda if r["status"] == "PLANEJADA")

    resposta = client.post(
        f"/api/v1/motorista/rotas/{nova['id']}/iniciar", headers=cenario["motorista"]
    )

    assert resposta.status_code == 409
    assert "andamento" in resposta.json()["mensagem"]


def test_chegada_exige_rota_iniciada(client: TestClient, cenario) -> None:
    rota = rota_atual(client, cenario)
    parada = next(p for p in rota["stops"] if p["stop_type"] == "ENTREGA")

    resposta = client.post(
        f"/api/v1/motorista/paradas/{parada['id']}/cheguei",
        headers=cenario["motorista"],
        json={},
    )

    assert resposta.status_code == 422
    assert "Inicie a rota" in resposta.json()["mensagem"]


def test_fluxo_completo_de_uma_parada(client: TestClient, cenario) -> None:
    rota = rota_atual(client, cenario)
    client.post(f"/api/v1/motorista/rotas/{rota['id']}/iniciar", headers=cenario["motorista"])

    rota = client.get(
        f"/api/v1/motorista/rotas/{rota['id']}", headers=cenario["motorista"]
    ).json()
    parada = next(p for p in rota["stops"] if p["stop_type"] == "ENTREGA")
    item = parada["items"][0]

    chegada = client.post(
        f"/api/v1/motorista/paradas/{parada['id']}/cheguei",
        headers=cenario["motorista"],
        json={"latitude": -20.455, "longitude": -54.61},
    )
    assert chegada.status_code == 200
    assert chegada.json()["status"] == "CHEGOU"
    assert chegada.json()["arrived_at"]

    entrega = client.post(
        f"/api/v1/motorista/entregas/{item['id']}/entregue",
        headers=cenario["motorista"],
        json={"recebedor": "Maria"},
    )
    assert entrega.status_code == 200

    # Parada com uma entrega so fecha assim que ela e resolvida.
    assert entrega.json()["status"] == "CONCLUIDA"
    assert entrega.json()["items"][0]["receiver_name"] == "Maria"


def test_insucesso_exige_motivo(client: TestClient, cenario) -> None:
    rota = rota_atual(client, cenario)
    client.post(f"/api/v1/motorista/rotas/{rota['id']}/iniciar", headers=cenario["motorista"])
    item = entregas_da_rota(rota)[0]

    sem_motivo = client.post(
        f"/api/v1/motorista/entregas/{item['id']}/nao-entregue",
        headers=cenario["motorista"],
        json={},
    )
    assert sem_motivo.status_code == 422

    com_motivo = client.post(
        f"/api/v1/motorista/entregas/{item['id']}/nao-entregue",
        headers=cenario["motorista"],
        json={"motivo": "CLIENTE_AUSENTE"},
    )
    assert com_motivo.status_code == 200


def test_motivo_outro_exige_descricao(client: TestClient, cenario) -> None:
    """Sem descricao o relatorio de insucesso nao explicaria nada — e e ele
    que a empresa usa contra reclamacao de cliente."""
    rota = rota_atual(client, cenario)
    client.post(f"/api/v1/motorista/rotas/{rota['id']}/iniciar", headers=cenario["motorista"])
    item = entregas_da_rota(rota)[0]

    resposta = client.post(
        f"/api/v1/motorista/entregas/{item['id']}/nao-entregue",
        headers=cenario["motorista"],
        json={"motivo": "OUTRO"},
    )

    assert resposta.status_code == 422


def test_progresso_avanca_a_cada_entrega(client: TestClient, cenario) -> None:
    rota = rota_atual(client, cenario)
    client.post(f"/api/v1/motorista/rotas/{rota['id']}/iniciar", headers=cenario["motorista"])

    itens = entregas_da_rota(rota)
    client.post(
        f"/api/v1/motorista/entregas/{itens[0]['id']}/entregue",
        headers=cenario["motorista"],
        json={},
    )

    atual = client.get(
        f"/api/v1/motorista/rotas/{rota['id']}", headers=cenario["motorista"]
    ).json()

    assert atual["progresso"]["concluidas"] == 1
    assert atual["progresso"]["restantes"] == len(PONTOS) - 1


# --------------------------------------------------------------------------- #
# Finalizacao — a regra que evita esconder servico nao feito
# --------------------------------------------------------------------------- #
def test_finalizar_marca_pendentes_como_nao_entregues(client: TestClient, cenario) -> None:
    """Entrega sem registro NAO vira "entregue" por omissao.

    Se virasse, a empresa acharia que o dia fechou e so descobriria o
    contrario quando o cliente ligasse cobrando.
    """
    rota = rota_atual(client, cenario)
    client.post(f"/api/v1/motorista/rotas/{rota['id']}/iniciar", headers=cenario["motorista"])

    itens = entregas_da_rota(rota)
    client.post(
        f"/api/v1/motorista/entregas/{itens[0]['id']}/entregue",
        headers=cenario["motorista"],
        json={},
    )

    resposta = client.post(
        f"/api/v1/motorista/rotas/{rota['id']}/finalizar", headers=cenario["motorista"]
    )
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "FINALIZADA"

    entregas = client.get("/api/v1/entregas", headers=cenario["admin"]).json()
    por_status = {}
    for e in entregas:
        por_status[e["status"]] = por_status.get(e["status"], 0) + 1

    assert por_status.get("ENTREGUE") == 1
    assert por_status.get("NAO_ENTREGUE") == len(PONTOS) - 1
    assert "ENTREGUE" in por_status


def test_historico_registra_quem_e_quando(client: TestClient, cenario) -> None:
    rota = rota_atual(client, cenario)
    client.post(f"/api/v1/motorista/rotas/{rota['id']}/iniciar", headers=cenario["motorista"])

    item = entregas_da_rota(rota)[0]
    client.post(
        f"/api/v1/motorista/entregas/{item['id']}/entregue",
        headers=cenario["motorista"],
        json={"latitude": -20.455, "longitude": -54.61},
    )

    eventos = client.get(
        f"/api/v1/entregas/{item['delivery_id']}/historico", headers=cenario["admin"]
    ).json()

    entregue = [e for e in eventos if e["to_status"] == "ENTREGUE"]
    assert entregue
    assert entregue[0]["latitude"] == -20.455


# --------------------------------------------------------------------------- #
# Painel
# --------------------------------------------------------------------------- #
def test_painel_reflete_a_operacao(client: TestClient, cenario) -> None:
    rota = rota_atual(client, cenario)
    client.post(f"/api/v1/motorista/rotas/{rota['id']}/iniciar", headers=cenario["motorista"])

    painel = client.get("/api/v1/painel", headers=cenario["admin"]).json()

    assert painel["entregas"]["total"] == len(PONTOS)
    assert painel["entregas"]["em_rota"] == len(PONTOS)
    assert painel["rotas"]["em_andamento"] == 1
    assert painel["rotas"]["motoristas_em_operacao"] == 1
    assert len(painel["rotas_ativas"]) == 1
    assert painel["bases"]


def test_painel_vazio_mostra_zeros_de_verdade(
    client: TestClient, criar_usuario, autenticar
) -> None:
    """Sem entregas cadastradas os numeros sao zero, nao valores de exemplo."""
    criar_usuario(email=ADMIN, role=Role.ADMIN)

    painel = client.get("/api/v1/painel", headers=autenticar(ADMIN)).json()

    assert painel["entregas"]["total"] == 0
    assert painel["rotas"]["total"] == 0
    assert painel["rotas_ativas"] == []
