"""Limite de tentativas de login, política de senha e registro de eventos."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.core.enums import Role
from app.models.seguranca import LoginAttempt, SecurityEvent
from tests.conftest import SENHA_PADRAO

ADMIN = "admin@britto.com.br"
MOTORISTA = "carlos@britto.com.br"
SENHA_FORTE = "caneca de barro antiga 3"


def _login(client: TestClient, email: str, senha: str):
    return client.post("/api/v1/auth/login", json={"email": email, "password": senha})


def _errar(client: TestClient, email: str, vezes: int) -> None:
    for _ in range(vezes):
        assert _login(client, email, "nao e a senha certa").status_code == 401


@pytest.fixture
def admin(client: TestClient, criar_usuario, autenticar):
    criar_usuario(email=ADMIN, role=Role.ADMIN, name="Bruno Admin")
    return autenticar(ADMIN)


@pytest.fixture
def motorista(criar_usuario):
    return criar_usuario(email=MOTORISTA, role=Role.MOTORISTA, name="Carlos Entregador")


# --------------------------------------------------------------------------- #
# Limite de tentativas
# --------------------------------------------------------------------------- #
def test_cinco_falhas_bloqueiam_a_conta_mesmo_com_a_senha_certa(client, motorista) -> None:
    """Se a senha certa entrasse durante o bloqueio, não seria bloqueio: o
    atacante só precisaria acertar dentro dele."""
    _errar(client, MOTORISTA, 5)

    resposta = _login(client, MOTORISTA, SENHA_PADRAO)

    assert resposta.status_code == 429
    assert int(resposta.headers["Retry-After"]) > 0
    assert "Tente de novo em" in resposta.json()["mensagem"]


def test_email_que_nao_existe_bloqueia_igual(client, motorista) -> None:
    """Bloquear só conta existente revelaria, pelo comportamento, quais
    contas existem. A resposta tem de ser a mesma."""
    _errar(client, "ninguem@britto.com.br", 5)
    _errar(client, MOTORISTA, 5)

    inexistente = _login(client, "ninguem@britto.com.br", "qualquer coisa aqui")
    existente = _login(client, MOTORISTA, "qualquer coisa aqui")

    assert inexistente.status_code == existente.status_code == 429
    assert inexistente.json()["mensagem"] == existente.json()["mensagem"]


def test_insistir_durante_o_bloqueio_nao_o_prolonga(client, motorista, db) -> None:
    """Senão quem ataca manteria o dono da conta trancado para sempre."""
    _errar(client, MOTORISTA, 5)
    for _ in range(10):
        assert _login(client, MOTORISTA, "chute durante o bloqueio").status_code == 429
    # As 5 falhas "envelhecem" além do bloqueio; as tentativas bloqueadas, não.
    db.execute(
        update(LoginAttempt)
        .where(LoginAttempt.motivo == "CREDENCIAL")
        .values(created_at=datetime.now(UTC) - timedelta(minutes=16))
    )
    db.commit()

    assert _login(client, MOTORISTA, SENHA_PADRAO).status_code == 200


def test_login_certo_zera_a_contagem(client, motorista) -> None:
    _errar(client, MOTORISTA, 4)
    assert _login(client, MOTORISTA, SENHA_PADRAO).status_code == 200
    _errar(client, MOTORISTA, 4)

    assert _login(client, MOTORISTA, SENHA_PADRAO).status_code == 200


def test_muitas_contas_erradas_do_mesmo_ip_bloqueiam_o_ip(client) -> None:
    """A senha comum testada em muitas contas: nenhuma conta chega a 5
    falhas, e o bloqueio por conta sozinho não pegaria."""
    for i in range(20):
        _errar(client, f"alvo{i}@britto.com.br", 1)

    assert _login(client, "mais.um@britto.com.br", "Senha123456").status_code == 429


def test_admin_desbloqueia_e_fica_registrado(client, admin, motorista, db) -> None:
    _errar(client, MOTORISTA, 5)
    bloqueadas = client.get("/api/v1/seguranca/bloqueios", headers=admin).json()
    assert [b["email"] for b in bloqueadas] == [MOTORISTA]
    assert bloqueadas[0]["nome"] == "Carlos Entregador"

    resposta = client.post(
        "/api/v1/seguranca/bloqueios/desbloquear", headers=admin, json={"email": MOTORISTA}
    )

    assert resposta.json() == []
    assert _login(client, MOTORISTA, SENHA_PADRAO).status_code == 200
    tipos = {e.tipo for e in db.query(SecurityEvent).all()}
    assert {"CONTA_BLOQUEADA", "CONTA_DESBLOQUEADA"} <= tipos


def test_motorista_nao_ve_a_seguranca(client, criar_usuario, autenticar) -> None:
    criar_usuario(email=MOTORISTA, role=Role.MOTORISTA)
    cabecalho = autenticar(MOTORISTA)

    assert client.get("/api/v1/seguranca/eventos", headers=cabecalho).status_code == 403


# --------------------------------------------------------------------------- #
# Política de senha
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "senha",
    ["SenhaForte123", "Flamengo@2024", "1234567890ab", "aaaaaaaaaaaa", "Carlos.2026!!"],
)
def test_senha_fraca_e_recusada_ao_criar_usuario(client, admin, senha) -> None:
    resposta = client.post(
        "/api/v1/usuarios",
        headers=admin,
        json={"name": "Carlos Entregador", "email": "novo@britto.com.br",
              "password": senha, "role": "MOTORISTA"},
    )

    assert resposta.status_code == 422
    assert resposta.json()["detalhes"]["problemas"]


def test_frase_longa_e_aceita(client, admin) -> None:
    """A política não exige símbolo nem maiúscula: frase longa é mais forte
    e mais fácil de lembrar do que `Senha@2024`."""
    resposta = client.post(
        "/api/v1/usuarios",
        headers=admin,
        json={"name": "Carlos", "email": "novo@britto.com.br",
              "password": "pão de queijo quente", "role": "MOTORISTA"},
    )

    assert resposta.status_code == 201


def test_troca_e_redefinicao_tambem_seguem_a_politica(client, admin, motorista) -> None:
    propria = client.post(
        "/api/v1/auth/senha",
        headers=admin,
        json={"current_password": SENHA_PADRAO, "new_password": "BrunoAdmin2026"},
    )
    redefinida = client.post(
        f"/api/v1/usuarios/{motorista.id}/senha",
        headers=admin,
        json={"new_password": "carlosentregador1"},
    )

    assert propria.status_code == 422
    assert redefinida.status_code == 422


def test_login_avisa_quando_a_senha_em_uso_e_fraca(client, criar_usuario) -> None:
    """Senha antiga, criada antes da política: continua entrando — trancar
    alguém fora por uma regra nova seria pior —, mas a tela pede a troca."""
    criar_usuario(email="antigo@britto.com.br", senha="SenhaForte123")
    criar_usuario(email="novo@britto.com.br", senha=SENHA_FORTE)

    fraca = _login(client, "antigo@britto.com.br", "SenhaForte123").json()
    forte = _login(client, "novo@britto.com.br", SENHA_FORTE).json()

    assert fraca["senha_fraca"] is True
    assert forte["senha_fraca"] is False


# --------------------------------------------------------------------------- #
# Eventos e cabeçalhos
# --------------------------------------------------------------------------- #
def test_mudanca_de_papel_registra_de_quem_para_quem(client, admin, motorista) -> None:
    client.patch(f"/api/v1/usuarios/{motorista.id}", headers=admin, json={"role": "ADMIN"})
    client.patch(f"/api/v1/usuarios/{motorista.id}", headers=admin, json={"active": False})

    eventos = client.get("/api/v1/seguranca/eventos", headers=admin).json()

    papel = next(e for e in eventos if e["tipo"] == "PAPEL_ALTERADO")
    assert papel["detalhe"] == {"de": "MOTORISTA", "para": "ADMIN"}
    assert papel["quem"] == "Bruno Admin"
    assert papel["sobre"] == "Carlos Entregador"
    assert any(e["tipo"] == "USUARIO_DESATIVADO" for e in eventos)


def test_cabecalhos_de_seguranca_nas_respostas_da_api(client, admin) -> None:
    resposta = client.get("/api/v1/auth/me", headers=admin)

    assert resposta.headers["X-Content-Type-Options"] == "nosniff"
    assert resposta.headers["X-Frame-Options"] == "DENY"
    assert resposta.headers["Cache-Control"] == "no-store"
    # HSTS só com HTTPS de verdade — e a suíte roda em HTTP.
    assert "Strict-Transport-Security" not in resposta.headers
