"""Relatórios: o que foi prometido, o que aconteceu, e a diferença.

Os dados são montados à mão, com horas escolhidas, porque o que se verifica
aqui é a CONTA — média, mediana, faixa de atraso. Com dados vindos do solver
o teste passaria a medir o solver.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.core.enums import Role
from app.models.base_location import BaseLocation
from app.models.delivery import Delivery
from app.models.driver import Driver
from app.models.route import Route, RoutePlan, RouteStop, RouteStopDelivery
from app.models.vehicle import Vehicle
from app.services import relatorios

ADMIN = "admin@britto.com.br"
DIA = date.today() - timedelta(days=1)
PERIODO = relatorios.Periodo(de=DIA - timedelta(days=7), ate=DIA)


FUSO = ZoneInfo("America/Campo_Grande")


def hora(h: int, m: int = 0, dia: date = DIA) -> datetime:
    """Hora de Campo Grande, onde a operação acontece."""
    return datetime(dia.year, dia.month, dia.day, h, m, tzinfo=FUSO)


@pytest.fixture
def admin(client: TestClient, criar_usuario, autenticar):
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    return autenticar(ADMIN)


@pytest.fixture
def base(db):
    b = BaseLocation(
        name="Loja", address="Av. Afonso Pena, 1500", latitude=-20.4697,
        longitude=-54.6201, geocode_status="MANUAL", is_default=True,
    )
    db.add(b)
    db.commit()
    return b


def montar_rota(
    db,
    base,
    *,
    motorista: str = "Carlos",
    dia: date = DIA,
    fonte: str = "OSRM",
    paradas: list[dict],
    distancia_m: int = 30000,
    inicio: datetime | None = None,
    fim: datetime | None = None,
) -> Route:
    """Uma rota executada, com os registros que o motorista teria deixado.

    Cada parada: `previsto`, `chegou`, `saiu` (datetimes ou None),
    `previsto_deslocamento_s`, e os desfechos das entregas em `itens`.
    """
    veiculo = Vehicle(name=f"Caminhao {motorista}", plate=f"{motorista[:3].upper()}1A11")
    condutor = Driver(name=motorista)
    # A fonte da matriz e do plano; a rota aponta para ele.
    plano = RoutePlan(base_id=base.id, date=dia, status="CONFIRMADO", matrix_source=fonte)
    db.add_all([veiculo, condutor, plano])
    db.flush()

    rota = Route(
        route_plan_id=plano.id,
        base_id=base.id, vehicle_id=veiculo.id, driver_id=condutor.id, date=dia,
        status="FINALIZADA", sequence_in_day=1,
        total_distance_m=distancia_m,
        started_at=inicio or hora(8, 0, dia),
        finished_at=fim or hora(17, 0, dia),
    )
    db.add(rota)
    db.flush()

    db.add(RouteStop(
        route_id=rota.id, stop_type="BASE_SAIDA", trip_number=1, sequence=0,
        label="Loja", latitude=base.latitude, longitude=base.longitude,
        estimated_arrival=hora(8, 0, dia), status="CONCLUIDA",
        departed_at=inicio or hora(8, 0, dia),
    ))

    for i, p in enumerate(paradas, start=1):
        parada = RouteStop(
            route_id=rota.id, stop_type="ENTREGA", trip_number=1, sequence=i,
            label=p.get("rotulo", f"Cliente {i}"), address=f"Rua {i}, 100",
            latitude=-20.45, longitude=-54.61,
            estimated_arrival=p.get("previsto"),
            arrived_at=p.get("chegou"),
            departed_at=p.get("saiu"),
            service_time_s=p.get("servico_s", 3600),
            duration_from_previous_s=p.get("previsto_deslocamento_s", 600),
            distance_from_previous_m=5000,
            status="CONCLUIDA" if p.get("chegou") or p.get("concluida") else "PENDENTE",
        )
        db.add(parada)
        db.flush()
        for j, item in enumerate(p.get("itens", [{"status": "ENTREGUE"}]), start=1):
            entrega = Delivery(
                address=f"Rua {i}, 100", recipient_name=p.get("rotulo", f"Cliente {i}"),
                latitude=-20.45, longitude=-54.61, geocode_status="MANUAL",
                scheduled_date=dia, status=item["status"],
            )
            db.add(entrega)
            db.flush()
            db.add(RouteStopDelivery(
                route_stop_id=parada.id, delivery_id=entrega.id, sequence_in_stop=j,
                status=item["status"], failure_reason=item.get("motivo"),
                receiver_name=item.get("recebedor"), notes=item.get("observacao"),
                delivered_at=p.get("saiu") if item["status"] == "ENTREGUE" else None,
            ))
    db.commit()
    return rota


# --------------------------------------------------------------------------- #
# Entregas e motivos
# --------------------------------------------------------------------------- #
def test_conta_entregues_nao_entregues_e_motivos(db, base) -> None:
    montar_rota(db, base, paradas=[
        {"itens": [{"status": "ENTREGUE"}, {"status": "ENTREGUE"}]},
        {"itens": [{"status": "NAO_ENTREGUE", "motivo": "CLIENTE_AUSENTE"}]},
        {"itens": [{"status": "NAO_ENTREGUE", "motivo": "CLIENTE_AUSENTE"}]},
        {"itens": [{"status": "NAO_ENTREGUE", "motivo": "RECUSA"}]},
    ])

    resumo = relatorios.entregas(db, PERIODO)

    assert (resumo["entregues"], resumo["nao_entregues"]) == (2, 3)
    assert resumo["taxa_sucesso"] == 0.4
    assert resumo["motivos"][0] == {"motivo": "CLIENTE_AUSENTE", "quantidade": 2}
    assert {"motivo": "RECUSA", "quantidade": 1} in resumo["motivos"]


def test_entrega_ainda_em_rota_nao_conta_como_fracasso(db, base) -> None:
    """A taxa sai sobre o que teve desfecho: senão o número do dia pioraria
    sozinho até a noite, só porque o caminhão ainda está na rua."""
    montar_rota(db, base, paradas=[
        {"itens": [{"status": "ENTREGUE"}]},
        {"itens": [{"status": "EM_ROTA"}]},
    ])

    resumo = relatorios.entregas(db, PERIODO)

    assert resumo["total"] == 2
    assert resumo["taxa_sucesso"] == 1.0


def test_periodo_recorta_o_que_entra(db, base) -> None:
    montar_rota(db, base, dia=DIA, paradas=[{"itens": [{"status": "ENTREGUE"}]}])
    montar_rota(db, base, motorista="Ana", dia=DIA - timedelta(days=30),
                paradas=[{"itens": [{"status": "ENTREGUE"}]}])

    assert relatorios.entregas(db, PERIODO)["entregues"] == 1
    largo = relatorios.Periodo(de=DIA - timedelta(days=60), ate=DIA)
    assert relatorios.entregas(db, largo)["entregues"] == 2


# --------------------------------------------------------------------------- #
# Pontualidade
# --------------------------------------------------------------------------- #
def test_classifica_o_atraso_por_faixa(db, base) -> None:
    montar_rota(db, base, paradas=[
        # 30 min adiantado, 5 min adiantado, 25 min atrasado, 2 h atrasado.
        {"previsto": hora(9, 0), "chegou": hora(8, 30), "saiu": hora(9, 30)},
        {"previsto": hora(10, 0), "chegou": hora(9, 55), "saiu": hora(10, 55)},
        {"previsto": hora(11, 0), "chegou": hora(11, 25), "saiu": hora(12, 25)},
        {"previsto": hora(12, 0), "chegou": hora(14, 0), "saiu": hora(15, 0)},
    ])

    p = relatorios.pontualidade(db, PERIODO)

    assert p["paradas"] == 4
    assert (p["adiantadas"], p["no_horario"], p["atrasadas"], p["muito_atrasadas"]) == (
        1, 1, 1, 1,
    )
    # -30, -5, +25, +120 min -> mediana 10 min.
    assert p["atraso_mediano_s"] == 600
    assert p["atraso_medio_s"] == round((-1800 - 300 + 1500 + 7200) / 4)


def test_parada_sem_hora_de_chegada_fica_de_fora_e_aparece_no_buraco(db, base) -> None:
    """Pontualidade sobre metade das paradas precisa dizer que é sobre
    metade — senão vira um número bonito sem lastro."""
    montar_rota(db, base, paradas=[
        {"previsto": hora(9, 0), "chegou": hora(9, 5), "saiu": hora(10, 0)},
        {"previsto": hora(11, 0), "chegou": None, "concluida": True},
    ])

    assert relatorios.pontualidade(db, PERIODO)["paradas"] == 1
    assert relatorios.paradas_sem_registro(db, PERIODO) == 1


# --------------------------------------------------------------------------- #
# Calibração: o palpite de 60 min está certo?
# --------------------------------------------------------------------------- #
def test_mede_o_tempo_real_de_parada_contra_o_planejado(db, base) -> None:
    montar_rota(db, base, paradas=[
        {"previsto": hora(9), "chegou": hora(9, 0), "saiu": hora(9, 30)},   # 30 min
        {"previsto": hora(10), "chegou": hora(10, 0), "saiu": hora(10, 40)},  # 40 min
        {"previsto": hora(11), "chegou": hora(11, 0), "saiu": hora(12, 20)},  # 80 min
    ])

    t = relatorios.tempo_de_parada(db, PERIODO)

    assert t["amostras"] == 3
    assert t["planejado_medio_s"] == 3600
    assert t["real_mediano_s"] == 2400
    assert t["real_medio_s"] == 3000


def test_parada_esquecida_aberta_nao_entra_na_calibracao(db, base) -> None:
    """Chegou às 9h e "saiu" às 22h é registro esquecido, não uma entrega de
    treze horas. Deixar entrar moveria a média que calibra o planejamento."""
    montar_rota(db, base, paradas=[
        {"previsto": hora(9), "chegou": hora(9, 0), "saiu": hora(9, 30)},
        {"previsto": hora(10), "chegou": hora(10, 0), "saiu": hora(22, 0)},
    ])

    t = relatorios.tempo_de_parada(db, PERIODO)

    assert t["amostras"] == 1
    assert t["real_medio_s"] == 1800


def test_chegada_e_saida_no_mesmo_minuto_nao_calibram(db, base) -> None:
    """O motorista que marca chegada e entrega de uma vez, no fim da parada,
    registra uma entrega de dois segundos. Entrando na conta, a mediana do
    tempo de parada despenca e o planejamento passa a prometer o impossível."""
    montar_rota(db, base, paradas=[
        {"previsto": hora(9), "chegou": hora(9, 0), "saiu": hora(9, 40)},
        {"previsto": hora(10), "chegou": hora(10, 0), "saiu": hora(10, 0)},
        {"previsto": hora(11), "chegou": hora(11, 0), "saiu": hora(11, 0)},
    ])

    t = relatorios.tempo_de_parada(db, PERIODO)

    assert t["amostras"] == 1
    assert t["real_mediano_s"] == 2400
    assert t["registros_em_bloco"] == 2


def test_rota_cancelada_nao_soma_quilometragem(db, base) -> None:
    """Plano descartado deixa a rota CANCELADA. Nenhum caminhão rodou aqueles
    quilômetros — somá-los inventaria operação que não houve."""
    executada = montar_rota(db, base, distancia_m=30000,
                            paradas=[{"itens": [{"status": "ENTREGUE"}]}])
    cancelada = montar_rota(db, base, motorista="Ana", distancia_m=99000,
                            paradas=[{"itens": [{"status": "PLANEJADA"}]}])
    cancelada.status = "CANCELADA"
    db.commit()

    r = relatorios.rotas(db, PERIODO)

    assert r["total"] == 1
    assert r["distancia_m"] == 30000
    assert executada.status == "FINALIZADA"


def test_compara_o_deslocamento_previsto_com_o_real_por_fonte(db, base) -> None:
    """A pergunta que a fase do trânsito deixou em aberto: o tempo com
    trânsito acerta mais que o de rua livre?"""
    # Rua livre: previu 10 min, levou 20 — metade do tempo real.
    montar_rota(db, base, fonte="OSRM", paradas=[
        {"previsto": hora(9), "chegou": hora(8, 20), "saiu": hora(9, 20),
         "previsto_deslocamento_s": 600},
        {"previsto": hora(10), "chegou": hora(9, 40), "saiu": hora(10, 40),
         "previsto_deslocamento_s": 600},
    ])
    # Com trânsito: previu 20 min, levou 20.
    montar_rota(db, base, motorista="Ana", fonte="GOOGLE_TRANSITO", paradas=[
        {"previsto": hora(9), "chegou": hora(8, 20), "saiu": hora(9, 20),
         "previsto_deslocamento_s": 1200},
        {"previsto": hora(10), "chegou": hora(9, 40), "saiu": hora(10, 40),
         "previsto_deslocamento_s": 1200},
    ])

    por_fonte = {d["fonte"]: d for d in relatorios.deslocamento(db, PERIODO)}

    assert por_fonte["OSRM"]["razao_mediana"] == 2.0
    assert por_fonte["GOOGLE_TRANSITO"]["razao_mediana"] == 1.0
    assert por_fonte["GOOGLE_TRANSITO"]["real_mediano_s"] == 1200


# --------------------------------------------------------------------------- #
# Recortes
# --------------------------------------------------------------------------- #
def test_por_motorista_compara_quem_entrega_e_quem_atrasa(db, base) -> None:
    montar_rota(db, base, motorista="Carlos", paradas=[
        {"previsto": hora(9), "chegou": hora(9, 10), "saiu": hora(10),
         "itens": [{"status": "ENTREGUE"}]},
    ])
    montar_rota(db, base, motorista="Ana", paradas=[
        {"previsto": hora(9), "chegou": hora(10, 0), "saiu": hora(11),
         "itens": [{"status": "NAO_ENTREGUE", "motivo": "RECUSA"}]},
    ])

    linhas = {m["nome"]: m for m in relatorios.por_motorista(db, PERIODO)}

    assert linhas["Carlos"]["taxa_sucesso"] == 1.0
    assert linhas["Carlos"]["atraso_medio_s"] == 600
    assert linhas["Ana"]["taxa_sucesso"] == 0.0
    assert linhas["Ana"]["atraso_medio_s"] == 3600


def test_por_dia_devolve_a_serie_do_periodo(db, base) -> None:
    montar_rota(db, base, dia=DIA, paradas=[{"itens": [{"status": "ENTREGUE"}]}])
    montar_rota(db, base, motorista="Ana", dia=DIA - timedelta(days=1), paradas=[
        {"itens": [{"status": "ENTREGUE"}, {"status": "NAO_ENTREGUE", "motivo": "AVARIA"}]},
    ])

    serie = relatorios.por_dia(db, PERIODO)

    assert [d["dia"] for d in serie] == [
        (DIA - timedelta(days=1)).isoformat(), DIA.isoformat()
    ]
    assert serie[0] == {
        "dia": (DIA - timedelta(days=1)).isoformat(), "entregues": 1, "nao_entregues": 1
    }


def test_rotas_somam_distancia_tempo_e_viagens(db, base) -> None:
    rota = montar_rota(db, base, distancia_m=42000, inicio=hora(8), fim=hora(16),
                       paradas=[{"itens": [{"status": "ENTREGUE"}]}])
    db.add(RouteStop(
        route_id=rota.id, stop_type="BASE_RECARGA", trip_number=2, sequence=90,
        label="Loja", latitude=base.latitude, longitude=base.longitude,
        estimated_arrival=hora(12), status="CONCLUIDA",
    ))
    db.commit()

    r = relatorios.rotas(db, PERIODO)

    assert r["total"] == 1
    assert r["distancia_m"] == 42000
    assert r["tempo_em_rota_s"] == 8 * 3600
    assert r["viagens"] == 2


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
def test_admin_le_o_relatorio_pela_api(client: TestClient, admin, db, base) -> None:
    montar_rota(db, base, paradas=[
        {"previsto": hora(9), "chegou": hora(9, 5), "saiu": hora(10),
         "itens": [{"status": "ENTREGUE"}]},
    ])

    corpo = client.get(
        "/api/v1/relatorios",
        headers=admin,
        params={"de": PERIODO.de.isoformat(), "ate": PERIODO.ate.isoformat()},
    ).json()

    assert corpo["entregas"]["entregues"] == 1
    assert corpo["pontualidade"]["no_horario"] == 1
    assert corpo["por_dia"][0]["dia"] == DIA.isoformat()
    assert corpo["paradas_sem_registro"] == 0


def test_periodo_invertido_e_recusado(client: TestClient, admin) -> None:
    resposta = client.get(
        "/api/v1/relatorios", headers=admin, params={"de": "2026-09-30", "ate": "2026-09-01"}
    )

    assert resposta.status_code == 422
    assert "depois" in resposta.json()["mensagem"]


def test_periodo_longo_demais_e_recusado(client: TestClient, admin) -> None:
    resposta = client.get(
        "/api/v1/relatorios", headers=admin, params={"de": "2020-01-01", "ate": "2026-01-01"}
    )

    assert resposta.status_code == 422


def test_csv_abre_no_excel_com_previsto_e_realizado(
    client: TestClient, admin, db, base
) -> None:
    montar_rota(db, base, paradas=[
        {"rotulo": "Marcenaria Sao Jorge", "previsto": hora(9), "chegou": hora(9, 30),
         "saiu": hora(10, 15),
         "itens": [{"status": "ENTREGUE", "recebedor": "Portaria"}]},
    ])

    resposta = client.get(
        "/api/v1/relatorios/entregas.csv",
        headers=admin,
        params={"de": PERIODO.de.isoformat(), "ate": PERIODO.ate.isoformat()},
    )

    assert resposta.status_code == 200
    assert "attachment" in resposta.headers["content-disposition"]
    texto = resposta.content.decode("utf-8")
    assert texto.startswith("﻿")  # o Excel precisa do BOM para os acentos
    linhas = texto.strip().splitlines()
    assert linhas[0].startswith("﻿data;rota;sequencia;cliente")
    campos = linhas[1].split(";")
    assert "Marcenaria Sao Jorge" in campos
    assert "Portaria" in campos
    assert "30" in campos  # 30 min de atraso
    assert "45" in campos  # 45 min parado na entrega
    # Hora local, como na tela — não UTC.
    assert f"{DIA.strftime('%d/%m/%Y')} 09:30" in campos


def test_motorista_nao_ve_relatorio(client: TestClient, criar_usuario, autenticar) -> None:
    criar_usuario(email="mot@britto.com.br", role=Role.MOTORISTA)

    resposta = client.get("/api/v1/relatorios", headers=autenticar("mot@britto.com.br"))

    assert resposta.status_code == 403
