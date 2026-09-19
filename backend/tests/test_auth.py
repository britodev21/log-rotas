"""Autenticacao, sessao e troca de senha."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.enums import Role
from tests.conftest import SENHA_PADRAO

EMAIL = "motorista@britto.com.br"


def test_login_valido_devolve_tokens_e_usuario(client: TestClient, criar_usuario) -> None:
    criar_usuario(email=EMAIL, role=Role.MOTORISTA)

    resposta = client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA_PADRAO}
    )

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["expires_in"] > 0
    assert corpo["user"]["role"] == Role.MOTORISTA.value
    # O hash da senha nunca pode escapar pela API.
    assert "password_hash" not in corpo["user"]


def test_login_aceita_email_em_maiusculas(client: TestClient, criar_usuario) -> None:
    criar_usuario(email=EMAIL)
    resposta = client.post(
        "/api/v1/auth/login", json={"email": EMAIL.upper(), "password": SENHA_PADRAO}
    )
    assert resposta.status_code == 200


def test_senha_errada_e_email_inexistente_dao_a_mesma_resposta(
    client: TestClient, criar_usuario
) -> None:
    """Respostas diferentes revelariam quais e-mails estao cadastrados."""
    criar_usuario(email=EMAIL)

    senha_errada = client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": "SenhaErrada123"}
    )
    email_inexistente = client.post(
        "/api/v1/auth/login",
        json={"email": "ninguem@britto.com.br", "password": SENHA_PADRAO},
    )

    assert senha_errada.status_code == email_inexistente.status_code == 401
    assert senha_errada.json()["mensagem"] == email_inexistente.json()["mensagem"]


def test_usuario_inativo_nao_entra(client: TestClient, criar_usuario) -> None:
    criar_usuario(email=EMAIL, active=False)
    resposta = client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA_PADRAO}
    )
    assert resposta.status_code == 401


def test_rota_protegida_exige_token(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer lixo"}).status_code
        == 401
    )


def test_me_devolve_o_usuario_do_token(client: TestClient, criar_usuario, autenticar) -> None:
    criar_usuario(email=EMAIL, name="Joao da Silva")
    resposta = client.get("/api/v1/auth/me", headers=autenticar(EMAIL))
    assert resposta.status_code == 200
    assert resposta.json()["name"] == "Joao da Silva"


def test_refresh_renova_a_sessao(client: TestClient, criar_usuario) -> None:
    criar_usuario(email=EMAIL)
    login = client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA_PADRAO}
    ).json()

    resposta = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login["refresh_token"]}
    )

    assert resposta.status_code == 200
    assert resposta.json()["access_token"]


def test_access_token_nao_serve_como_refresh(client: TestClient, criar_usuario) -> None:
    """Trocar um tipo de token pelo outro daria ao access a validade do refresh."""
    criar_usuario(email=EMAIL)
    login = client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA_PADRAO}
    ).json()

    resposta = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": login["access_token"]}
    )

    assert resposta.status_code == 401


def test_refresh_token_nao_abre_rota_protegida(client: TestClient, criar_usuario) -> None:
    criar_usuario(email=EMAIL)
    login = client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA_PADRAO}
    ).json()

    resposta = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login['refresh_token']}"},
    )

    assert resposta.status_code == 401


def test_troca_de_senha_derruba_as_sessoes_antigas(client: TestClient, criar_usuario) -> None:
    criar_usuario(email=EMAIL)
    antigo = client.post(
        "/api/v1/auth/login", json={"email": EMAIL, "password": SENHA_PADRAO}
    ).json()
    cabecalho_antigo = {"Authorization": f"Bearer {antigo['access_token']}"}

    troca = client.post(
        "/api/v1/auth/senha",
        headers=cabecalho_antigo,
        json={"current_password": SENHA_PADRAO, "new_password": "NovaSenha456"},
    )
    assert troca.status_code == 200

    # O token antigo morre...
    assert client.get("/api/v1/auth/me", headers=cabecalho_antigo).status_code == 401
    # ...e o par devolvido pela troca continua valendo.
    novo = {"Authorization": f"Bearer {troca.json()['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=novo).status_code == 200

    assert (
        client.post(
            "/api/v1/auth/login", json={"email": EMAIL, "password": "NovaSenha456"}
        ).status_code
        == 200
    )


def test_troca_de_senha_exige_a_senha_atual(
    client: TestClient, criar_usuario, autenticar
) -> None:
    criar_usuario(email=EMAIL)
    resposta = client.post(
        "/api/v1/auth/senha",
        headers=autenticar(EMAIL),
        json={"current_password": "ChutePuro123", "new_password": "NovaSenha456"},
    )
    assert resposta.status_code == 401
