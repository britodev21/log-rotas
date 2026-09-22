"""Gestao de usuarios e separacao de papeis.

O motorista tem acesso a operacao dele, nao ao sistema. Estes testes existem
para que uma rota administrativa nunca fique aberta para o perfil errado por
descuido.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.enums import Role
from tests.conftest import SENHA_PADRAO

ADMIN = "admin@britto.com.br"
MOTORISTA = "motorista@britto.com.br"

NOVO_USUARIO = {
    "name": "Carlos Motorista",
    "email": "carlos@britto.com.br",
    "password": SENHA_PADRAO,
    "role": Role.MOTORISTA.value,
}


def test_motorista_nao_acessa_rotas_administrativas(
    client: TestClient, criar_usuario, autenticar
) -> None:
    criar_usuario(email=MOTORISTA, role=Role.MOTORISTA)
    cabecalho = autenticar(MOTORISTA)

    assert client.get("/api/v1/usuarios", headers=cabecalho).status_code == 403
    assert (
        client.post("/api/v1/usuarios", headers=cabecalho, json=NOVO_USUARIO).status_code == 403
    )
    assert client.get("/api/v1/configuracoes", headers=cabecalho).status_code == 403


def test_admin_cadastra_usuario(client: TestClient, criar_usuario, autenticar) -> None:
    criar_usuario(email=ADMIN, role=Role.ADMIN)

    resposta = client.post("/api/v1/usuarios", headers=autenticar(ADMIN), json=NOVO_USUARIO)

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["email"] == "carlos@britto.com.br"

    # E o usuario criado consegue entrar.
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "carlos@britto.com.br", "password": SENHA_PADRAO},
    )
    assert login.status_code == 200


def test_email_duplicado_e_conflito(client: TestClient, criar_usuario, autenticar) -> None:
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    cabecalho = autenticar(ADMIN)

    client.post("/api/v1/usuarios", headers=cabecalho, json=NOVO_USUARIO)
    repetido = client.post("/api/v1/usuarios", headers=cabecalho, json=NOVO_USUARIO)

    assert repetido.status_code == 409
    assert repetido.json()["erro"] == "conflito"


def test_email_duplicado_ignora_maiusculas(
    client: TestClient, criar_usuario, autenticar
) -> None:
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    cabecalho = autenticar(ADMIN)

    client.post("/api/v1/usuarios", headers=cabecalho, json=NOVO_USUARIO)
    repetido = client.post(
        "/api/v1/usuarios",
        headers=cabecalho,
        json={**NOVO_USUARIO, "email": "CARLOS@britto.com.br"},
    )

    assert repetido.status_code == 409


def test_nao_deixa_o_sistema_sem_administrador(
    client: TestClient, criar_usuario, autenticar
) -> None:
    """Sem esta trava, um clique tranca a empresa para fora do proprio sistema."""
    admin = criar_usuario(email=ADMIN, role=Role.ADMIN)
    cabecalho = autenticar(ADMIN)

    desativar = client.patch(
        f"/api/v1/usuarios/{admin.id}", headers=cabecalho, json={"active": False}
    )
    assert desativar.status_code == 422

    rebaixar = client.patch(
        f"/api/v1/usuarios/{admin.id}",
        headers=cabecalho,
        json={"role": Role.MOTORISTA.value},
    )
    assert rebaixar.status_code == 422


def test_com_outro_admin_ativo_a_alteracao_e_permitida(
    client: TestClient, criar_usuario, autenticar
) -> None:
    admin = criar_usuario(email=ADMIN, role=Role.ADMIN)
    criar_usuario(email="outro@britto.com.br", role=Role.ADMIN)

    resposta = client.patch(
        f"/api/v1/usuarios/{admin.id}",
        headers=autenticar(ADMIN),
        json={"role": Role.MOTORISTA.value},
    )

    assert resposta.status_code == 200
    assert resposta.json()["role"] == Role.MOTORISTA.value


def test_desativar_usuario_encerra_a_sessao_dele(
    client: TestClient, criar_usuario, autenticar
) -> None:
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    motorista = criar_usuario(email=MOTORISTA, role=Role.MOTORISTA)

    cabecalho_motorista = autenticar(MOTORISTA)
    assert client.get("/api/v1/auth/me", headers=cabecalho_motorista).status_code == 200

    client.patch(
        f"/api/v1/usuarios/{motorista.id}",
        headers=autenticar(ADMIN),
        json={"active": False},
    )

    assert client.get("/api/v1/auth/me", headers=cabecalho_motorista).status_code == 401


def test_admin_redefine_senha_e_derruba_a_sessao(
    client: TestClient, criar_usuario, autenticar
) -> None:
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    motorista = criar_usuario(email=MOTORISTA, role=Role.MOTORISTA)
    cabecalho_motorista = autenticar(MOTORISTA)

    resposta = client.post(
        f"/api/v1/usuarios/{motorista.id}/senha",
        headers=autenticar(ADMIN),
        json={"new_password": "caneca de barro antiga 3"},
    )
    assert resposta.status_code == 200

    assert client.get("/api/v1/auth/me", headers=cabecalho_motorista).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": MOTORISTA, "password": "caneca de barro antiga 3"},
        ).status_code
        == 200
    )


def test_filtro_por_papel_na_listagem(client: TestClient, criar_usuario, autenticar) -> None:
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    criar_usuario(email=MOTORISTA, role=Role.MOTORISTA)

    resposta = client.get(
        "/api/v1/usuarios",
        headers=autenticar(ADMIN),
        params={"role": Role.MOTORISTA.value},
    )

    assert resposta.status_code == 200
    emails = [u["email"] for u in resposta.json()]
    assert emails == [MOTORISTA]
