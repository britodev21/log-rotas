"""Cadastros: bases, veiculos, motoristas e clientes.

Todos exclusivos do administrador. O motorista nao precisa nem deve ver a
frota, a carteira de clientes ou os colegas — ele recebe a propria rota, e
so isso.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import AdminUser, DbSession
from app.schemas.cadastros import (
    BaseLocationCreate,
    BaseLocationRead,
    BaseLocationUpdate,
    CustomerCreate,
    CustomerRead,
    CustomerUpdate,
    DriverCreate,
    DriverRead,
    DriverUpdate,
    VehicleCreate,
    VehicleRead,
    VehicleUpdate,
)
from app.services.cadastros_service import (
    BaseLocationService,
    CustomerService,
    DriverService,
    VehicleService,
)

Ativo = Annotated[bool | None, Query(description="Filtrar por situacao.")]
Busca = Annotated[str | None, Query(max_length=120, description="Busca textual.")]


# --------------------------------------------------------------------------- #
# Bases
# --------------------------------------------------------------------------- #
bases_router = APIRouter(prefix="/bases", tags=["Bases"])


@bases_router.get("", response_model=list[BaseLocationRead], summary="Listar bases")
def listar_bases(
    session: DbSession, _: AdminUser, active: Ativo = None, search: Busca = None
) -> list[BaseLocationRead]:
    registros = BaseLocationService(session).listar(active=active, search=search)
    return [BaseLocationRead.model_validate(r) for r in registros]


@bases_router.post(
    "",
    response_model=BaseLocationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar base",
)
def criar_base(
    payload: BaseLocationCreate, session: DbSession, _: AdminUser
) -> BaseLocationRead:
    """A primeira base cadastrada vira a padrao automaticamente."""
    return BaseLocationRead.model_validate(BaseLocationService(session).criar(payload))


@bases_router.get("/{base_id}", response_model=BaseLocationRead, summary="Detalhe da base")
def obter_base(base_id: int, session: DbSession, _: AdminUser) -> BaseLocationRead:
    return BaseLocationRead.model_validate(BaseLocationService(session).get(base_id))


@bases_router.patch("/{base_id}", response_model=BaseLocationRead, summary="Alterar base")
def atualizar_base(
    base_id: int, payload: BaseLocationUpdate, session: DbSession, _: AdminUser
) -> BaseLocationRead:
    """Marcar esta base como padrao desmarca a anterior; desativar limpa o padrao.

    Alterar o endereco sem informar coordenada descarta a coordenada antiga e
    devolve o registro para a fila de geocodificacao.
    """
    return BaseLocationRead.model_validate(
        BaseLocationService(session).atualizar(base_id, payload)
    )


# --------------------------------------------------------------------------- #
# Veiculos
# --------------------------------------------------------------------------- #
vehicles_router = APIRouter(prefix="/veiculos", tags=["Veiculos"])


@vehicles_router.get("", response_model=list[VehicleRead], summary="Listar veiculos")
def listar_veiculos(
    session: DbSession, _: AdminUser, active: Ativo = None, search: Busca = None
) -> list[VehicleRead]:
    registros = VehicleService(session).listar(active=active, search=search)
    return [VehicleRead.model_validate(r) for r in registros]


@vehicles_router.post(
    "",
    response_model=VehicleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar veiculo",
)
def criar_veiculo(payload: VehicleCreate, session: DbSession, _: AdminUser) -> VehicleRead:
    """As capacidades sao opcionais — preencha as que a operacao usa.

    Cada uma preenchida pode virar restricao do otimizador na Fase 6; as
    vazias sao ignoradas.
    """
    return VehicleRead.model_validate(VehicleService(session).criar(payload))


@vehicles_router.get("/{vehicle_id}", response_model=VehicleRead, summary="Detalhe do veiculo")
def obter_veiculo(vehicle_id: int, session: DbSession, _: AdminUser) -> VehicleRead:
    return VehicleRead.model_validate(VehicleService(session).get(vehicle_id))


@vehicles_router.patch("/{vehicle_id}", response_model=VehicleRead, summary="Alterar veiculo")
def atualizar_veiculo(
    vehicle_id: int, payload: VehicleUpdate, session: DbSession, _: AdminUser
) -> VehicleRead:
    return VehicleRead.model_validate(VehicleService(session).atualizar(vehicle_id, payload))


# --------------------------------------------------------------------------- #
# Motoristas
# --------------------------------------------------------------------------- #
drivers_router = APIRouter(prefix="/motoristas", tags=["Motoristas"])


@drivers_router.get("", response_model=list[DriverRead], summary="Listar motoristas")
def listar_motoristas(
    session: DbSession, _: AdminUser, active: Ativo = None, search: Busca = None
) -> list[DriverRead]:
    registros = DriverService(session).listar(active=active, search=search)
    return [DriverRead.model_validate(r) for r in registros]


@drivers_router.post(
    "",
    response_model=DriverRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar motorista",
)
def criar_motorista(payload: DriverCreate, session: DbSession, _: AdminUser) -> DriverRead:
    """O vinculo com um usuario e opcional.

    Motorista terceirizado, ou ainda sem acesso criado, existe normalmente
    sem `user_id` e ja pode ser atribuido a uma rota.
    """
    return DriverRead.model_validate(DriverService(session).criar(payload))


@drivers_router.get("/{driver_id}", response_model=DriverRead, summary="Detalhe do motorista")
def obter_motorista(driver_id: int, session: DbSession, _: AdminUser) -> DriverRead:
    return DriverRead.model_validate(DriverService(session).get(driver_id))


@drivers_router.patch("/{driver_id}", response_model=DriverRead, summary="Alterar motorista")
def atualizar_motorista(
    driver_id: int, payload: DriverUpdate, session: DbSession, _: AdminUser
) -> DriverRead:
    return DriverRead.model_validate(DriverService(session).atualizar(driver_id, payload))


# --------------------------------------------------------------------------- #
# Clientes
# --------------------------------------------------------------------------- #
customers_router = APIRouter(prefix="/clientes", tags=["Clientes"])


@customers_router.get("", response_model=list[CustomerRead], summary="Listar clientes")
def listar_clientes(
    session: DbSession, _: AdminUser, active: Ativo = None, search: Busca = None
) -> list[CustomerRead]:
    registros = CustomerService(session).listar(active=active, search=search)
    return [CustomerRead.model_validate(r) for r in registros]


@customers_router.post(
    "",
    response_model=CustomerRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cadastrar cliente",
)
def criar_cliente(payload: CustomerCreate, session: DbSession, _: AdminUser) -> CustomerRead:
    return CustomerRead.model_validate(CustomerService(session).criar(payload))


@customers_router.get(
    "/{customer_id}", response_model=CustomerRead, summary="Detalhe do cliente"
)
def obter_cliente(customer_id: int, session: DbSession, _: AdminUser) -> CustomerRead:
    return CustomerRead.model_validate(CustomerService(session).get(customer_id))


@customers_router.patch(
    "/{customer_id}", response_model=CustomerRead, summary="Alterar cliente"
)
def atualizar_cliente(
    customer_id: int, payload: CustomerUpdate, session: DbSession, _: AdminUser
) -> CustomerRead:
    """Alterar o endereco sem informar coordenada devolve o cliente para a
    fila de geocodificacao — a coordenada antiga apontaria para outro lugar."""
    return CustomerRead.model_validate(CustomerService(session).atualizar(customer_id, payload))
