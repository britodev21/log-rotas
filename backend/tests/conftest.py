"""Infraestrutura dos testes.

Os testes rodam contra um Postgres de verdade (log_rotas_test), nao contra
SQLite. O motivo e direto: o schema usa CHECK constraints, IDENTITY e
timestamptz, e um teste que passa no SQLite mas quebra no Postgres nao prova
nada sobre o sistema que vai rodar na empresa.

Cada teste roda dentro de uma transacao que sofre rollback no final. Os
commits dos services viram SAVEPOINT, entao o banco volta limpo mesmo com a
camada de servico commitando de verdade.
"""

from __future__ import annotations

import os

# Precisa vir antes de qualquer import de app.*: get_settings() e cacheado e
# le o ambiente na primeira chamada. Variavel de ambiente tem prioridade
# sobre o .env, entao o banco de teste nunca encosta no banco de trabalho.
os.environ["DATABASE_URL"] = (
    "postgresql+psycopg://postgres:postgres@localhost:5432/log_rotas_test"
)
os.environ.setdefault("JWT_SECRET", "chave-de-teste-com-tamanho-suficiente-para-passar")
os.environ.setdefault("ENVIRONMENT", "test")
# Sem isto o .env com DEBUG=true faz o SQLAlchemy despejar todo o SQL no
# relatorio, e a falha de verdade fica enterrada sob centenas de linhas.
os.environ.setdefault("DEBUG", "false")
# Sem isto a suite tentaria falar com o OSRM publico: testes ficariam
# lentos, dependeriam de rede e falhariam quando o servico estivesse fora.
os.environ.setdefault("MATRIX_PROVIDER", "haversine")
# Sem isto a suite leria o .env da maquina e chamaria o Google de verdade —
# com a chave real, gastando cota a cada rodada de testes. Atribuicao, nao
# setdefault: precisa vencer o .env.
os.environ["TRAFFIC_PROVIDER"] = ""
os.environ["GOOGLE_MAPS_API_KEY"] = ""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.enums import Role
from app.core.security import hash_password
from app.main import app
from app.models import Base, User

# Frase, nao "Senha123": a politica de senha (app/core/senha.py) recusa
# as senhas comuns, e o repositorio e publico.
SENHA_PADRAO = "tijolo azul da serra 42"

engine = create_engine(os.environ["DATABASE_URL"], future=True)


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db() -> Iterator[Session]:
    connection = engine.connect()
    transaction = connection.begin()
    # create_savepoint faz com que session.commit() dentro dos services vire
    # RELEASE SAVEPOINT, preservando o rollback externo.
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(db: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Fabricas
# --------------------------------------------------------------------------- #
@pytest.fixture
def criar_usuario(db: Session):
    def _criar(
        *,
        email: str,
        role: Role = Role.ADMIN,
        senha: str = SENHA_PADRAO,
        active: bool = True,
        name: str = "Usuario de Teste",
    ) -> User:
        user = User(
            name=name,
            email=email.lower(),
            password_hash=hash_password(senha),
            role=role.value,
            active=active,
        )
        db.add(user)
        db.commit()
        return user

    return _criar


@pytest.fixture
def autenticar(client: TestClient):
    """Faz login e devolve o header Authorization pronto."""

    def _autenticar(email: str, senha: str = SENHA_PADRAO) -> dict[str, str]:
        resposta = client.post("/api/v1/auth/login", json={"email": email, "password": senha})
        assert resposta.status_code == 200, resposta.text
        return {"Authorization": f"Bearer {resposta.json()['access_token']}"}

    return _autenticar
