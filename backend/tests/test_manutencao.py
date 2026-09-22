"""Limpeza automática: o que apaga, o que guarda, e que roda uma vez só."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.enums import Role
from app.models.base_location import BaseLocation
from app.models.geocode_cache import GeocodeCache
from app.models.route import Route
from app.models.route_position import RoutePosition
from app.models.seguranca import LoginAttempt, SecurityEvent
from app.models.vehicle import Vehicle
from app.services import manutencao
from tests.conftest import engine

AGORA = datetime.now(UTC)
FUSO = ZoneInfo("America/Campo_Grande")


def _dias(n: int) -> datetime:
    return AGORA - timedelta(days=n)


@pytest.fixture
def rota(db):
    base = BaseLocation(name="Loja", latitude=-20.46, longitude=-54.62, geocode_status="MANUAL")
    veiculo = Vehicle(name="Caminhao", plate="ABC1D23")
    db.add_all([base, veiculo])
    db.flush()
    r = Route(base_id=base.id, vehicle_id=veiculo.id, date=date.today(), status="FINALIZADA")
    db.add(r)
    db.flush()
    return r


def _posicao(rota, dias: int) -> RoutePosition:
    return RoutePosition(
        route_id=rota.id, latitude=-20.4, longitude=-54.6, recorded_at=_dias(dias)
    )


def _cache(chave: str, status: str, quando: datetime, endereco: str = "rua x") -> GeocodeCache:
    return GeocodeCache(
        address_hash=chave.ljust(64, "0"), normalized_address=endereco, provider="teste",
        status=status, created_at=quando, updated_at=quando,
    )


def test_apaga_so_o_que_passou_do_prazo(db, rota) -> None:
    db.add_all([
        _posicao(rota, 100),
        _posicao(rota, 10),
        LoginAttempt(email="a@b.com", sucesso=False, motivo="CREDENCIAL",
                     created_at=_dias(200)),
        LoginAttempt(email="a@b.com", sucesso=True, motivo="OK", created_at=_dias(1)),
        SecurityEvent(tipo="PAPEL_ALTERADO", created_at=_dias(800)),
        SecurityEvent(tipo="PAPEL_ALTERADO", created_at=_dias(1)),
        # Endereço que falhou há 40 dias: sai, para ser tentado de novo.
        _cache("a", "FALHOU", _dias(40)),
        # Sucesso antigo: fica — é o cache que poupa o limite do provedor.
        _cache("b", "OK", _dias(400)),
        # Conferência do Google de 40 dias: sai, só servia na hora de salvar.
        _cache("c", "OK", _dias(40), endereco="place:ChIJxyz"),
    ])
    db.flush()

    execucao = manutencao.limpar(db, origem=manutencao.MANUAL)

    assert execucao.resultado == {
        "posicoes": 1, "tentativas_login": 1, "eventos_seguranca": 1,
        "cache_falhas": 1, "cache_google": 1,
    }
    assert db.query(RoutePosition).count() == 1
    assert db.query(LoginAttempt).count() == 1
    assert db.query(SecurityEvent).count() == 1
    assert [c.status for c in db.query(GeocodeCache).all()] == ["OK"]


def test_agendada_roda_uma_vez_por_dia(db) -> None:
    """Com vários processos, cada um tem o seu agendador: o registro diário
    é o que impede a mesma limpeza de rodar duas vezes."""
    primeira = manutencao.limpar(db, origem=manutencao.AGENDADA)
    segunda = manutencao.limpar(db, origem=manutencao.AGENDADA)

    assert primeira is not None
    assert segunda is None


def test_manual_roda_mesmo_depois_da_agendada(db) -> None:
    manutencao.limpar(db, origem=manutencao.AGENDADA)

    assert manutencao.limpar(db, origem=manutencao.MANUAL) is not None


def test_outra_limpeza_em_andamento_nao_duplica(db) -> None:
    """Outro processo segurando o bloqueio: esta execução não faz nada."""
    with engine.connect() as outro_processo:
        outro_processo.execute(
            text("SELECT pg_advisory_lock(:k)"), {"k": manutencao.CHAVE_DO_BLOQUEIO}
        )
        try:
            assert manutencao.limpar(db, origem=manutencao.MANUAL) is None
        finally:
            outro_processo.execute(
                text("SELECT pg_advisory_unlock(:k)"), {"k": manutencao.CHAVE_DO_BLOQUEIO}
            )


@pytest.mark.parametrize(
    ("hora_local", "ja_rodou", "esperado"),
    [
        (2, False, False),  # antes das 3h
        (3, False, True),  # na hora
        (15, False, True),  # servidor estava desligado às 3h: roda quando voltar
        (15, True, False),  # já rodou hoje
    ],
)
def test_quando_a_limpeza_agendada_roda(
    db, monkeypatch, hora_local, ja_rodou, esperado
) -> None:
    monkeypatch.setattr(
        manutencao, "get_settings",
        lambda: SimpleNamespace(limpeza_hora=3, default_timezone="America/Campo_Grande",
                                retencao_posicoes_dias=90, retencao_tentativas_login_dias=180,
                                retencao_eventos_seguranca_dias=730),
    )
    agora_local = datetime.now(FUSO).replace(hour=hora_local, minute=10)
    if ja_rodou:
        manutencao.limpar(db, origem=manutencao.AGENDADA, agora=agora_local.astimezone(UTC))

    assert manutencao.deve_rodar(db, agora_local) is esperado


def test_admin_limpa_pela_api_e_fica_registrado(
    client: TestClient, criar_usuario, autenticar
) -> None:
    criar_usuario(email="admin@britto.com.br", role=Role.ADMIN)
    admin = autenticar("admin@britto.com.br")

    corpo = client.post("/api/v1/manutencao/limpar", headers=admin).json()

    assert corpo["ultimas"][0]["origem"] == "MANUAL"
    assert corpo["retencao_posicoes_dias"] == 90


def test_motorista_nao_limpa(client: TestClient, criar_usuario, autenticar) -> None:
    criar_usuario(email="mot@britto.com.br", role=Role.MOTORISTA)

    resposta = client.post(
        "/api/v1/manutencao/limpar", headers=autenticar("mot@britto.com.br")
    )

    assert resposta.status_code == 403
