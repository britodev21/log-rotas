"""Primeiro acesso.

A regra critica aqui e que a rota se feche depois do primeiro usuario. Se ela
continuasse aberta, qualquer pessoa na internet criaria um ADMIN no sistema da
empresa.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.enums import Role
from tests.conftest import SENHA_PADRAO

PAYLOAD = {
    "company_name": "Britto Moveis e Corrimao",
    "admin_name": "Administrador",
    "admin_email": "admin@britto.com.br",
    "admin_password": SENHA_PADRAO,
}


def test_sistema_vazio_pede_configuracao(client: TestClient) -> None:
    resposta = client.get("/api/v1/setup/status")
    assert resposta.status_code == 200
    assert resposta.json()["needs_setup"] is True


def test_primeiro_acesso_cria_empresa_e_admin_e_ja_autentica(client: TestClient) -> None:
    resposta = client.post("/api/v1/setup", json=PAYLOAD)
    assert resposta.status_code == 201, resposta.text

    corpo = resposta.json()
    assert corpo["user"]["email"] == "admin@britto.com.br"
    assert corpo["user"]["role"] == Role.ADMIN.value
    assert corpo["access_token"] and corpo["refresh_token"]

    # A configuracao da empresa nasce junto, na mesma transacao.
    cabecalho = {"Authorization": f"Bearer {corpo['access_token']}"}
    config = client.get("/api/v1/configuracoes", headers=cabecalho)
    assert config.status_code == 200
    assert config.json()["company_name"] == "Britto Moveis e Corrimao"

    assert client.get("/api/v1/setup/status").json()["needs_setup"] is False


def test_segundo_primeiro_acesso_e_recusado(client: TestClient, criar_usuario) -> None:
    criar_usuario(email="ja@existe.com")

    resposta = client.post("/api/v1/setup", json=PAYLOAD)

    assert resposta.status_code == 409
    assert resposta.json()["erro"] == "conflito"


def test_senha_curta_no_primeiro_acesso_e_recusada(client: TestClient) -> None:
    resposta = client.post("/api/v1/setup", json={**PAYLOAD, "admin_password": "123"})
    assert resposta.status_code == 422
    assert client.get("/api/v1/setup/status").json()["needs_setup"] is True


def test_email_do_admin_e_normalizado_para_minusculas(client: TestClient) -> None:
    resposta = client.post(
        "/api/v1/setup", json={**PAYLOAD, "admin_email": "  ADMIN@Britto.COM.BR "}
    )
    assert resposta.status_code == 201
    assert resposta.json()["user"]["email"] == "admin@britto.com.br"
