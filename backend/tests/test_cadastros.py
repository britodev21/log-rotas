"""Cadastros: bases, veiculos, motoristas e clientes.

Os testes cobrem as regras que, se quebrarem, produzem dado silenciosamente
errado — nao o CRUD em si. Um POST que grava e um GET que le nao precisam de
teste; uma coordenada que sobrevive a troca de endereco, sim.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.enums import Role

ADMIN = "admin@britto.com.br"
MOTORISTA = "motorista@britto.com.br"


@pytest.fixture
def admin(client: TestClient, criar_usuario, autenticar):
    criar_usuario(email=ADMIN, role=Role.ADMIN)
    return autenticar(ADMIN)


# --------------------------------------------------------------------------- #
# Permissoes
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "caminho", ["/api/v1/bases", "/api/v1/veiculos", "/api/v1/motoristas", "/api/v1/clientes"]
)
def test_motorista_nao_acessa_cadastros(
    client: TestClient, criar_usuario, autenticar, caminho
) -> None:
    """O motorista recebe a propria rota; frota e carteira de clientes nao
    sao da conta dele."""
    criar_usuario(email=MOTORISTA, role=Role.MOTORISTA)
    cabecalho = autenticar(MOTORISTA)

    assert client.get(caminho, headers=cabecalho).status_code == 403
    assert client.post(caminho, headers=cabecalho, json={}).status_code == 403


@pytest.mark.parametrize(
    "caminho", ["/api/v1/bases", "/api/v1/veiculos", "/api/v1/motoristas", "/api/v1/clientes"]
)
def test_cadastros_exigem_autenticacao(client: TestClient, caminho) -> None:
    assert client.get(caminho).status_code == 401


# --------------------------------------------------------------------------- #
# Bases
# --------------------------------------------------------------------------- #
def test_primeira_base_vira_padrao_sozinha(client: TestClient, admin) -> None:
    resposta = client.post("/api/v1/bases", headers=admin, json={"name": "Loja Centro"})
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["is_default"] is True


def test_marcar_outra_base_como_padrao_desmarca_a_anterior(client: TestClient, admin) -> None:
    """Duas bases padrao ao mesmo tempo deixariam o planejador sem criterio."""
    primeira = client.post("/api/v1/bases", headers=admin, json={"name": "Loja"}).json()
    segunda = client.post("/api/v1/bases", headers=admin, json={"name": "Fabrica"}).json()

    assert primeira["is_default"] is True
    assert segunda["is_default"] is False

    client.patch(f"/api/v1/bases/{segunda['id']}", headers=admin, json={"is_default": True})

    bases = {b["id"]: b for b in client.get("/api/v1/bases", headers=admin).json()}
    assert bases[segunda["id"]]["is_default"] is True
    assert bases[primeira["id"]]["is_default"] is False


def test_desativar_base_limpa_o_padrao(client: TestClient, admin) -> None:
    """Base inativa como padrao seria oferecida pelo planejador e falharia."""
    base = client.post("/api/v1/bases", headers=admin, json={"name": "Loja"}).json()
    assert base["is_default"] is True

    resposta = client.patch(
        f"/api/v1/bases/{base['id']}", headers=admin, json={"active": False}
    )

    assert resposta.status_code == 200
    assert resposta.json()["is_default"] is False


def test_coordenada_pela_metade_e_recusada(client: TestClient, admin) -> None:
    resposta = client.post(
        "/api/v1/bases",
        headers=admin,
        json={"name": "Loja", "latitude": -20.46},
    )
    assert resposta.status_code == 422


# --------------------------------------------------------------------------- #
# Coordenada x endereco — a regra que mais evita rota errada
# --------------------------------------------------------------------------- #
def test_informar_coordenada_marca_como_manual(client: TestClient, admin) -> None:
    """Pino posto a mao nunca pode ser sobrescrito pela geocodificacao."""
    resposta = client.post(
        "/api/v1/clientes",
        headers=admin,
        json={
            "name": "Marcenaria Sao Jorge",
            "address": "Rua 14 de Julho, 1500",
            "latitude": -20.4697,
            "longitude": -54.6201,
        },
    )

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["geocode_status"] == "MANUAL"


def test_trocar_endereco_descarta_a_coordenada_antiga(client: TestClient, admin) -> None:
    """Sem esta regra, editar o endereco manteria o pino no lugar anterior e a
    rota seria calculada para o endereco errado, sem nenhum aviso."""
    cliente = client.post(
        "/api/v1/clientes",
        headers=admin,
        json={
            "name": "Construtora Aurora",
            "address": "Rua A, 100",
            "latitude": -20.4697,
            "longitude": -54.6201,
        },
    ).json()
    assert cliente["geocode_status"] == "MANUAL"

    resposta = client.patch(
        f"/api/v1/clientes/{cliente['id']}",
        headers=admin,
        json={"address": "Avenida B, 2500"},
    )

    corpo = resposta.json()
    assert corpo["geocode_status"] == "PENDENTE"
    assert corpo["latitude"] is None
    assert corpo["longitude"] is None


def test_trocar_endereco_com_coordenada_nova_continua_manual(client: TestClient, admin) -> None:
    cliente = client.post(
        "/api/v1/clientes",
        headers=admin,
        json={"name": "Cliente", "address": "Rua A, 100"},
    ).json()

    resposta = client.patch(
        f"/api/v1/clientes/{cliente['id']}",
        headers=admin,
        json={"address": "Rua B, 200", "latitude": -20.5, "longitude": -54.6},
    )

    assert resposta.json()["geocode_status"] == "MANUAL"
    assert resposta.json()["latitude"] == -20.5


def test_alterar_outro_campo_nao_mexe_na_coordenada(client: TestClient, admin) -> None:
    cliente = client.post(
        "/api/v1/clientes",
        headers=admin,
        json={
            "name": "Cliente",
            "address": "Rua A, 100",
            "latitude": -20.4697,
            "longitude": -54.6201,
        },
    ).json()

    resposta = client.patch(
        f"/api/v1/clientes/{cliente['id']}", headers=admin, json={"phone": "67999990000"}
    )

    assert resposta.json()["geocode_status"] == "MANUAL"
    assert resposta.json()["latitude"] == -20.4697


# --------------------------------------------------------------------------- #
# Veiculos
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("informada", "gravada"),
    [
        ("abc1234", "ABC1234"),
        ("ABC-1234", "ABC1234"),
        (" abc1d23 ", "ABC1D23"),
    ],
)
def test_placa_e_normalizada(client: TestClient, admin, informada, gravada) -> None:
    """Placa com mascara e sem mascara nao podem virar dois veiculos."""
    resposta = client.post(
        "/api/v1/veiculos", headers=admin, json={"name": "Caminhao", "plate": informada}
    )
    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["plate"] == gravada


@pytest.mark.parametrize("placa", ["ABC12", "12345678", "A1C1234", ""])
def test_placa_invalida_e_recusada(client: TestClient, admin, placa) -> None:
    resposta = client.post(
        "/api/v1/veiculos", headers=admin, json={"name": "Caminhao", "plate": placa}
    )
    assert resposta.status_code == 422


def test_placa_duplicada_e_conflito_mesmo_com_mascara(client: TestClient, admin) -> None:
    client.post(
        "/api/v1/veiculos", headers=admin, json={"name": "Caminhao 1", "plate": "ABC1234"}
    )

    resposta = client.post(
        "/api/v1/veiculos", headers=admin, json={"name": "Caminhao 2", "plate": "abc-1234"}
    )

    assert resposta.status_code == 409
    assert resposta.json()["erro"] == "conflito"


def test_capacidades_sao_opcionais(client: TestClient, admin) -> None:
    """Ainda nao se sabe o que limita a carga da Britto: peso, volume ou
    comprimento. Exigir qualquer uma delas obrigaria a inventar numero."""
    resposta = client.post(
        "/api/v1/veiculos", headers=admin, json={"name": "Caminhao", "plate": "ABC1234"}
    )

    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["capacity_weight_kg"] is None
    assert corpo["capacity_volume_m3"] is None
    assert corpo["capacity_length_m"] is None
    assert corpo["crew_size"] == 1


def test_capacidade_negativa_e_recusada(client: TestClient, admin) -> None:
    resposta = client.post(
        "/api/v1/veiculos",
        headers=admin,
        json={"name": "Caminhao", "plate": "ABC1234", "capacity_weight_kg": -100},
    )
    assert resposta.status_code == 422


# --------------------------------------------------------------------------- #
# Motoristas
# --------------------------------------------------------------------------- #
def test_motorista_pode_existir_sem_acesso_ao_sistema(client: TestClient, admin) -> None:
    """Terceirizado, ou ainda sem login criado, precisa poder receber rota."""
    resposta = client.post(
        "/api/v1/motoristas", headers=admin, json={"name": "Joao Terceirizado"}
    )

    assert resposta.status_code == 201, resposta.text
    assert resposta.json()["user_id"] is None


def test_vincular_usuario_administrador_e_recusado(
    client: TestClient, admin, criar_usuario
) -> None:
    """Erro de categoria: o admin passaria a aparecer como quem leva carga."""
    outro_admin = criar_usuario(email="outro@britto.com.br", role=Role.ADMIN)

    resposta = client.post(
        "/api/v1/motoristas",
        headers=admin,
        json={"name": "Nao deveria", "user_id": outro_admin.id},
    )

    assert resposta.status_code == 422
    assert "motorista" in resposta.json()["mensagem"].lower()


def test_mesmo_usuario_nao_vira_dois_motoristas(
    client: TestClient, admin, criar_usuario
) -> None:
    usuario = criar_usuario(email=MOTORISTA, role=Role.MOTORISTA)

    primeiro = client.post(
        "/api/v1/motoristas",
        headers=admin,
        json={"name": "Carlos", "user_id": usuario.id},
    )
    assert primeiro.status_code == 201

    segundo = client.post(
        "/api/v1/motoristas",
        headers=admin,
        json={"name": "Carlos de novo", "user_id": usuario.id},
    )

    assert segundo.status_code == 409


def test_vincular_usuario_inexistente_e_404(client: TestClient, admin) -> None:
    resposta = client.post(
        "/api/v1/motoristas", headers=admin, json={"name": "Fantasma", "user_id": 99999}
    )
    assert resposta.status_code == 404


def test_motorista_traz_os_dados_do_usuario_vinculado(
    client: TestClient, admin, criar_usuario
) -> None:
    usuario = criar_usuario(email=MOTORISTA, role=Role.MOTORISTA, name="Carlos Entregador")

    resposta = client.post(
        "/api/v1/motoristas",
        headers=admin,
        json={"name": "Carlos Entregador", "user_id": usuario.id},
    )

    assert resposta.json()["user"]["email"] == MOTORISTA


# --------------------------------------------------------------------------- #
# Clientes
# --------------------------------------------------------------------------- #
def test_documento_duplicado_e_conflito(client: TestClient, admin) -> None:
    client.post(
        "/api/v1/clientes",
        headers=admin,
        json={"name": "Cliente A", "document": "12345678901"},
    )

    resposta = client.post(
        "/api/v1/clientes",
        headers=admin,
        json={"name": "Cliente B", "document": "123.456.789-01"},
    )

    assert resposta.status_code == 409


def test_varios_clientes_podem_ficar_sem_documento(client: TestClient, admin) -> None:
    """O indice de unicidade e parcial justamente para permitir isto."""
    for nome in ("Cliente A", "Cliente B", "Cliente C"):
        resposta = client.post("/api/v1/clientes", headers=admin, json={"name": nome})
        assert resposta.status_code == 201, resposta.text


def test_telefone_guardado_apenas_com_digitos(client: TestClient, admin) -> None:
    """Guardar "(67) 99999-0000" e "67999990000" como valores diferentes
    tornaria qualquer busca pouco confiavel."""
    resposta = client.post(
        "/api/v1/clientes",
        headers=admin,
        json={"name": "Cliente", "phone": "(67) 99999-0000"},
    )
    assert resposta.json()["phone"] == "67999990000"


# --------------------------------------------------------------------------- #
# Listagem
# --------------------------------------------------------------------------- #
def test_filtro_por_situacao_e_busca(client: TestClient, admin) -> None:
    client.post("/api/v1/clientes", headers=admin, json={"name": "Marcenaria Alfa"})
    client.post(
        "/api/v1/clientes",
        headers=admin,
        json={"name": "Construtora Beta", "active": False},
    )

    ativos = client.get("/api/v1/clientes", headers=admin, params={"active": True}).json()
    assert [c["name"] for c in ativos] == ["Marcenaria Alfa"]

    busca = client.get("/api/v1/clientes", headers=admin, params={"search": "beta"}).json()
    assert [c["name"] for c in busca] == ["Construtora Beta"]
