"""Entregas e a maquina de estados.

A maquina de estados e a regra mais critica do sistema: e ela que impede
uma entrega voltar de ENTREGUE para PENDENTE, ou uma rota ser iniciada duas
vezes. Erro aqui nao quebra a tela — produz relatorio que nao fecha, semanas
depois, sem ninguem conseguir reconstituir o que aconteceu.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.enums import Role
from app.services import status_machine

ADMIN = "admin@britto.com.br"
HOJE = date.today().isoformat()


@pytest.fixture
def admin(client: TestClient, criar_usuario, autenticar):
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    return autenticar(ADMIN)


@pytest.fixture
def entrega(client: TestClient, admin):
    resposta = client.post(
        "/api/v1/entregas",
        headers=admin,
        json={
            "address": "Rua 14 de Julho, 1500",
            "recipient_name": "Joana",
            "scheduled_date": HOJE,
        },
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def mudar(client, admin, entrega_id, status, **extra):
    return client.post(
        f"/api/v1/entregas/{entrega_id}/status",
        headers=admin,
        json={"status": status, **extra},
    )


# --------------------------------------------------------------------------- #
# Maquina de estados — testada direto, sem passar por HTTP
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("de", "para"),
    [
        ("PENDENTE", "PLANEJADA"),
        ("PLANEJADA", "EM_ROTA"),
        ("PLANEJADA", "PENDENTE"),  # plano descartado
        ("EM_ROTA", "CHEGOU"),
        ("EM_ROTA", "ENTREGUE"),  # entregou sem marcar chegada
        ("CHEGOU", "ENTREGUE"),
        ("CHEGOU", "NAO_ENTREGUE"),
        ("NAO_ENTREGUE", "PENDENTE"),  # reagendou
    ],
)
def test_transicoes_permitidas(de, para) -> None:
    assert status_machine.pode("entrega", de, para)


@pytest.mark.parametrize(
    ("de", "para"),
    [
        ("ENTREGUE", "PENDENTE"),
        ("ENTREGUE", "NAO_ENTREGUE"),
        ("PENDENTE", "ENTREGUE"),  # pularia a rota inteira
        ("PENDENTE", "EM_ROTA"),  # sem ter sido planejada
        ("CANCELADA", "ENTREGUE"),
    ],
)
def test_transicoes_proibidas(de, para) -> None:
    assert not status_machine.pode("entrega", de, para)


def test_entregue_e_estado_final() -> None:
    assert status_machine.e_final("entrega", "ENTREGUE")


def test_rota_nao_volta_de_finalizada() -> None:
    assert status_machine.e_final("rota", "FINALIZADA")
    assert status_machine.pode("rota", "PLANEJADA", "INICIADA")
    assert not status_machine.pode("rota", "FINALIZADA", "INICIADA")


def test_plano_confirmado_nao_volta() -> None:
    """Desfazer um plano confirmado e cancelar as rotas, nao reabrir o plano:
    elas ja podem ter comecado."""
    assert status_machine.e_final("plano", "CONFIRMADO")


# --------------------------------------------------------------------------- #
# Transicoes pela API
# --------------------------------------------------------------------------- #
def test_transicao_invalida_responde_409_com_os_permitidos(
    client: TestClient, admin, entrega
) -> None:
    resposta = mudar(client, admin, entrega["id"], "ENTREGUE")

    assert resposta.status_code == 409
    corpo = resposta.json()
    assert corpo["erro"] == "transicao_invalida"
    # A resposta diz o que ERA possivel: sem isso o cliente da API fica
    # adivinhando qual o proximo passo valido.
    assert "PLANEJADA" in corpo["detalhes"]["permitidos"]


def test_nao_entregue_exige_motivo(client: TestClient, admin, entrega) -> None:
    """Insucesso sem motivo nao vira relatorio."""
    mudar(client, admin, entrega["id"], "PLANEJADA")
    mudar(client, admin, entrega["id"], "EM_ROTA")

    sem_motivo = mudar(client, admin, entrega["id"], "NAO_ENTREGUE")
    assert sem_motivo.status_code == 422

    com_motivo = mudar(client, admin, entrega["id"], "NAO_ENTREGUE", reason="CLIENTE_AUSENTE")
    assert com_motivo.status_code == 200
    assert com_motivo.json()["status"] == "NAO_ENTREGUE"


def test_motivo_outro_exige_descricao(client: TestClient, admin, entrega) -> None:
    mudar(client, admin, entrega["id"], "PLANEJADA")
    mudar(client, admin, entrega["id"], "EM_ROTA")

    sem_texto = mudar(client, admin, entrega["id"], "NAO_ENTREGUE", reason="OUTRO")
    assert sem_texto.status_code == 422

    com_texto = mudar(
        client,
        admin,
        entrega["id"],
        "NAO_ENTREGUE",
        reason="OUTRO",
        notes="Rua interditada por obra.",
    )
    assert com_texto.status_code == 200


def test_historico_registra_cada_passo(client: TestClient, admin, entrega) -> None:
    """E o que permite responder semanas depois por que nao foi entregue."""
    mudar(client, admin, entrega["id"], "PLANEJADA")
    mudar(client, admin, entrega["id"], "EM_ROTA")
    mudar(client, admin, entrega["id"], "CHEGOU")
    mudar(client, admin, entrega["id"], "NAO_ENTREGUE", reason="CLIENTE_AUSENTE")

    eventos = client.get(f"/api/v1/entregas/{entrega['id']}/historico", headers=admin).json()

    caminho = [e["to_status"] for e in eventos]
    assert caminho == ["PENDENTE", "PLANEJADA", "EM_ROTA", "CHEGOU", "NAO_ENTREGUE"]
    assert eventos[-1]["reason"] == "CLIENTE_AUSENTE"
    assert eventos[-1]["from_status"] == "CHEGOU"


# --------------------------------------------------------------------------- #
# Cadastro
# --------------------------------------------------------------------------- #
def test_entrega_sem_endereco_e_sem_cliente_e_recusada(client: TestClient, admin) -> None:
    """Entrega sem destino nao tem para onde ir."""
    resposta = client.post("/api/v1/entregas", headers=admin, json={"scheduled_date": HOJE})
    assert resposta.status_code == 422


def test_entrega_herda_endereco_do_cliente(client: TestClient, admin) -> None:
    """Copia, nao referencia: o cliente pode mudar de endereco depois, e a
    entrega precisa guardar para onde ela foi de fato."""
    cliente = client.post(
        "/api/v1/clientes",
        headers=admin,
        json={
            "name": "Marcenaria Alfa",
            "address": "Avenida Bandeirantes, 900",
            "phone": "67999990000",
            "latitude": -20.47,
            "longitude": -54.62,
            "ponto_confirmado": True,
        },
    ).json()

    resposta = client.post(
        "/api/v1/entregas",
        headers=admin,
        json={"customer_id": cliente["id"], "scheduled_date": HOJE},
    )

    assert resposta.status_code == 201, resposta.text
    corpo = resposta.json()
    assert corpo["address"] == "Avenida Bandeirantes, 900"
    assert corpo["recipient_name"] == "Marcenaria Alfa"
    assert corpo["latitude"] == -20.47
    # A confirmacao viaja junto com a coordenada: quem ja marcou o portao
    # deste cliente nao marca de novo a cada pedido.
    assert corpo["geocode_status"] == "MANUAL"


def test_endereco_proprio_prevalece_sobre_o_do_cliente(client: TestClient, admin) -> None:
    """Entrega em obra, num endereco diferente do cadastro."""
    cliente = client.post(
        "/api/v1/clientes",
        headers=admin,
        json={"name": "Construtora", "address": "Escritorio, 100"},
    ).json()

    corpo = client.post(
        "/api/v1/entregas",
        headers=admin,
        json={
            "customer_id": cliente["id"],
            "address": "Obra - Rua Nova, 45",
            "scheduled_date": HOJE,
        },
    ).json()

    assert corpo["address"] == "Obra - Rua Nova, 45"


def test_janela_de_horario_invertida_e_recusada(client: TestClient, admin) -> None:
    """Janela impossivel so seria descoberta na otimizacao, como "sem
    solucao" — mensagem inutil para quem digitou o horario trocado."""
    resposta = client.post(
        "/api/v1/entregas",
        headers=admin,
        json={
            "address": "Rua A, 1",
            "scheduled_date": HOJE,
            "time_window_start": "14:00",
            "time_window_end": "09:00",
        },
    )
    assert resposta.status_code == 422


def test_medidas_sao_opcionais(client: TestClient, admin, entrega) -> None:
    assert entrega["weight_kg"] is None
    assert entrega["volume_m3"] is None
    assert entrega["length_m"] is None
    assert entrega["required_crew"] == 1
    assert entrega["service_time_minutes"] is None


# --------------------------------------------------------------------------- #
# Trava de edicao
# --------------------------------------------------------------------------- #
def test_entrega_em_rota_trava_campos_de_planejamento(
    client: TestClient, admin, entrega
) -> None:
    """Mudar o peso de uma carga que ja esta no caminhao invalidaria a rota
    em silencio — o veiculo foi escolhido contando com aquele numero."""
    mudar(client, admin, entrega["id"], "PLANEJADA")
    mudar(client, admin, entrega["id"], "EM_ROTA")

    resposta = client.patch(
        f"/api/v1/entregas/{entrega['id']}", headers=admin, json={"weight_kg": 500}
    )

    assert resposta.status_code == 422
    assert "weight_kg" in resposta.json()["detalhes"]["campos_bloqueados"]


def test_entrega_em_rota_ainda_aceita_observacao(client: TestClient, admin, entrega) -> None:
    """O que nao afeta o planejamento continua editavel: o motorista pode
    precisar registrar um ponto de referencia no meio do caminho."""
    mudar(client, admin, entrega["id"], "PLANEJADA")
    mudar(client, admin, entrega["id"], "EM_ROTA")

    resposta = client.patch(
        f"/api/v1/entregas/{entrega['id']}",
        headers=admin,
        json={"notes": "Portao azul, fundos."},
    )

    assert resposta.status_code == 200


# --------------------------------------------------------------------------- #
# Listagem
# --------------------------------------------------------------------------- #
def test_filtros_de_listagem(client: TestClient, admin) -> None:
    amanha = (date.today() + timedelta(days=1)).isoformat()

    client.post(
        "/api/v1/entregas",
        headers=admin,
        json={"address": "Hoje urgente", "scheduled_date": HOJE, "priority": "URGENTE"},
    )
    client.post(
        "/api/v1/entregas",
        headers=admin,
        json={"address": "Amanha normal", "scheduled_date": amanha},
    )

    de_hoje = client.get("/api/v1/entregas", headers=admin, params={"data": HOJE}).json()
    assert [e["address"] for e in de_hoje] == ["Hoje urgente"]

    urgentes = client.get(
        "/api/v1/entregas", headers=admin, params={"priority": "URGENTE"}
    ).json()
    assert len(urgentes) == 1

    sem_coord = client.get(
        "/api/v1/entregas", headers=admin, params={"sem_coordenada": True}
    ).json()
    assert len(sem_coord) == 2


def test_ordenacao_coloca_urgente_no_topo(client: TestClient, admin) -> None:
    """Ordem alfabetica poria ALTA antes de URGENTE e BAIXA antes de NORMAL."""
    for prioridade in ("BAIXA", "URGENTE", "NORMAL", "ALTA"):
        client.post(
            "/api/v1/entregas",
            headers=admin,
            json={
                "address": f"Entrega {prioridade}",
                "scheduled_date": HOJE,
                "priority": prioridade,
            },
        )

    entregas = client.get("/api/v1/entregas", headers=admin, params={"data": HOJE}).json()

    assert [e["priority"] for e in entregas] == ["URGENTE", "ALTA", "NORMAL", "BAIXA"]


def test_resumo_conta_por_status(client: TestClient, admin, entrega) -> None:
    resumo = client.get("/api/v1/entregas/resumo", headers=admin).json()

    assert resumo["total"] == 1
    assert resumo["por_status"]["PENDENTE"] == 1
    assert resumo["sem_coordenada"] == 1


def test_motorista_nao_acessa_entregas(client: TestClient, criar_usuario, autenticar) -> None:
    criar_usuario(email="mot@britto.com.br", role=Role.MOTORISTA)
    cabecalho = autenticar("mot@britto.com.br")
    assert client.get("/api/v1/entregas", headers=cabecalho).status_code == 403
