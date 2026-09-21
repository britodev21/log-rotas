"""Regras de negocio dos cadastros: bases, veiculos, motoristas e clientes."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.enums import GeocodePrecision, GeocodeStatus, Role
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.geocoding.service import chave_lugar
from app.models.base_location import BaseLocation
from app.models.customer import Customer
from app.models.driver import Driver
from app.models.geocode_cache import GeocodeCache
from app.models.vehicle import Vehicle
from app.repositories.cadastros_repository import (
    BaseLocationRepository,
    CustomerRepository,
    DriverRepository,
    VehicleRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.cadastros import (
    BaseLocationCreate,
    BaseLocationUpdate,
    CustomerCreate,
    CustomerUpdate,
    DriverCreate,
    DriverUpdate,
    VehicleCreate,
    VehicleUpdate,
)

logger = logging.getLogger(__name__)


def _aplicar(registro: Any, dados: dict[str, Any], *, ignorar: set[str] | None = None) -> None:
    """Copia os campos enviados para o registro.

    Usa `exclude_unset` na origem, entao campo ausente permanece como esta e
    campo enviado como null e realmente apagado — a diferenca entre "nao
    mexi nisso" e "quero limpar isso".
    """
    ignorar = ignorar or set()
    for campo, valor in dados.items():
        if campo not in ignorar:
            setattr(registro, campo, valor)


@dataclass(frozen=True)
class OrigemDoPonto:
    """De onde veio a coordenada recebida, ja conferido pelo servidor."""

    #: Uma pessoa marcou o ponto no mapa.
    confirmado: bool = False
    #: Precisao que o SERVIDOR conseguiu provar (cache do Google ou cliente
    #: herdado). Nunca vem direto do navegador.
    precisao: str | None = None
    provedor: str | None = None

    def ou(self, outra: OrigemDoPonto) -> OrigemDoPonto:
        return self if (self.confirmado or self.precisao) else outra


#: Uma coordenada so conta como "a mesma que o Google devolveu" se bater ate
#: a quinta casa decimal (~1 m). O banco guarda seis.
_TOLERANCIA_GRAUS = 1e-5


def tirar_origem(session: Session, dados: dict[str, Any]) -> OrigemDoPonto:
    """Retira do payload o que nao e coluna e decide a origem do ponto.

    Precisa rodar ANTES de `Modelo(**dados)`, que recusaria as chaves.

    O navegador pode dizer "escolhi este lugar no Google" (`google_place_id`),
    mas nao pode dizer "e exato". Quem diz e o servidor: procura o lugar no
    proprio cache — gravado quando o Google respondeu — e so aceita a
    precisao de la se a coordenada recebida for a MESMA. Se a pessoa mexeu
    no pino, isso e `ponto_confirmado`, e vale mais.

    Sem essa conferencia, qualquer cliente da API poderia gravar uma
    coordenada qualquer como EXATO e passar pela barreira do planejamento.
    """
    confirmado = bool(dados.pop("ponto_confirmado", False))
    place_id = dados.pop("google_place_id", None)
    precisao_herdada = dados.pop("_precisao_herdada", None)
    provedor_herdado = dados.pop("_provedor_herdado", None)

    if confirmado:
        return OrigemDoPonto(confirmado=True)

    lat, lon = dados.get("latitude"), dados.get("longitude")
    if lat is None or lon is None:
        return OrigemDoPonto()

    if place_id:
        registro = session.get(GeocodeCache, chave_lugar(place_id))
        if (
            registro is not None
            and registro.latitude is not None
            and abs(float(registro.latitude) - float(lat)) <= _TOLERANCIA_GRAUS
            and abs(float(registro.longitude) - float(lon)) <= _TOLERANCIA_GRAUS
        ):
            return OrigemDoPonto(precisao=registro.precision, provedor="google")

    if precisao_herdada:
        return OrigemDoPonto(precisao=precisao_herdada, provedor=provedor_herdado)

    return OrigemDoPonto()


def _reavaliar_geocodificacao(
    registro: Any, dados: dict[str, Any], origem: OrigemDoPonto | None = None
) -> None:
    """Mantem coordenada e endereco coerentes entre si.

    Tres situacoes, e a ordem importa:

    1. Veio coordenada E alguem confirmou o ponto no mapa -> MANUAL, que a
       geocodificacao automatica nunca sobrescreve.
    2. Veio coordenada sem confirmacao -> e um palpite do geocodificador.
       Fica gravada, porque serve para abrir o mapa no lugar certo, mas
       marcada como aproximada — e o planejamento a recusa.
    3. Mudou o endereco sem coordenada nenhuma -> a antiga aponta para outro
       lugar. E descartada e o registro volta para PENDENTE.

    A distincao entre 1 e 2 e recente e corrige um defeito serio: o
    formulario de entrega localiza o endereco sozinho, e o resultado era
    gravado como MANUAL. O sistema registrava "um humano marcou este ponto"
    quando nenhum humano tinha olhado para o mapa — e era justamente essa
    marca que autorizava a entrega a entrar em rota.

    Em Campo Grande isso nao e hipotese: o provedor gratuito resolve no
    nivel da RUA quase sempre (ver app/services/precisao.py), entao o pino
    automatico costuma estar a quarteiroes do portao.

    Sem a regra 3, editar "Rua A, 100" para "Rua B, 500" manteria o pino na
    Rua A, e a rota seria calculada para o endereco errado sem nenhum aviso.
    """
    informou_coordenada = (
        dados.get("latitude") is not None and dados.get("longitude") is not None
    )
    mudou_endereco = "address" in dados

    origem = origem or OrigemDoPonto()

    if informou_coordenada:
        if origem.confirmado:
            registro.geocode_status = GeocodeStatus.MANUAL.value
            registro.geocode_precision = None
            registro.geocode_provider = None
        else:
            # Sem precisao provada pelo servidor, RUA e o piso honesto.
            # Errar para "impreciso" custa uma confirmacao; errar para
            # "exato" custa uma entrega.
            registro.geocode_status = GeocodeStatus.OK.value
            registro.geocode_precision = origem.precisao or GeocodePrecision.RUA.value
            registro.geocode_provider = origem.provedor
            if origem.provedor:
                registro.geocoded_at = datetime.now(UTC)
        registro.geocode_error = None
        return

    if mudou_endereco:
        registro.latitude = None
        registro.longitude = None
        registro.geocode_status = GeocodeStatus.PENDENTE.value
        registro.geocode_precision = None
        registro.geocode_provider = None
        registro.geocode_error = None
        registro.geocoded_at = None


# --------------------------------------------------------------------------- #
# Bases
# --------------------------------------------------------------------------- #
class BaseLocationService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = BaseLocationRepository(session)

    def get(self, base_id: int) -> BaseLocation:
        base = self.repo.get(base_id)
        if base is None:
            raise NotFoundError("Base nao encontrada.")
        return base

    def listar(self, **filtros) -> list[BaseLocation]:
        return self.repo.listar(**filtros)

    def criar(self, payload: BaseLocationCreate) -> BaseLocation:
        dados = payload.model_dump()
        origem = tirar_origem(self.session, dados)
        # A primeira base cadastrada vira padrao sozinha: um sistema com uma
        # unica base e nenhuma marcada como padrao so geraria atrito no
        # planejador, sem informar nada.
        primeira = self.repo.contar() == 0
        dados["is_default"] = dados["is_default"] or primeira

        base = BaseLocation(**dados)
        _reavaliar_geocodificacao(base, dados, origem)

        if base.is_default:
            self.repo.limpar_padrao()

        self.repo.add(base)
        self.session.commit()
        logger.info("Base %s criada (padrao=%s).", base.id, base.is_default)
        return base

    def atualizar(self, base_id: int, payload: BaseLocationUpdate) -> BaseLocation:
        base = self.get(base_id)
        dados = payload.model_dump(exclude_unset=True)
        origem = tirar_origem(self.session, dados)

        _aplicar(base, dados)
        _reavaliar_geocodificacao(base, dados, origem)

        # Base inativa nao pode continuar sendo a padrao: o planejador a
        # ofereceria por default e falharia ao montar a rota.
        if base.active is False:
            base.is_default = False
        elif dados.get("is_default") is True:
            self.repo.limpar_padrao(exceto_id=base.id)
            base.is_default = True

        self.session.commit()
        return base


# --------------------------------------------------------------------------- #
# Veiculos
# --------------------------------------------------------------------------- #
class VehicleService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = VehicleRepository(session)

    def get(self, vehicle_id: int) -> Vehicle:
        veiculo = self.repo.get(vehicle_id)
        if veiculo is None:
            raise NotFoundError("Veiculo nao encontrado.")
        return veiculo

    def listar(self, **filtros) -> list[Vehicle]:
        return self.repo.listar(**filtros)

    def criar(self, payload: VehicleCreate) -> Vehicle:
        dados = payload.model_dump()
        self._garantir_placa_livre(dados["plate"])

        veiculo = self.repo.add(Vehicle(**dados))
        self.session.commit()
        logger.info("Veiculo %s criado (placa %s).", veiculo.id, veiculo.plate)
        return veiculo

    def atualizar(self, vehicle_id: int, payload: VehicleUpdate) -> Vehicle:
        veiculo = self.get(vehicle_id)
        dados = payload.model_dump(exclude_unset=True)

        if "plate" in dados and dados["plate"] != veiculo.plate:
            self._garantir_placa_livre(dados["plate"], excluir_id=veiculo.id)

        _aplicar(veiculo, dados)
        self.session.commit()
        return veiculo

    def _garantir_placa_livre(self, placa: str, *, excluir_id: int | None = None) -> None:
        if self.repo.existe_campo("plate", placa, excluir_id=excluir_id):
            raise ConflictError(f"Ja existe um veiculo com a placa {placa}.")


# --------------------------------------------------------------------------- #
# Motoristas
# --------------------------------------------------------------------------- #
class DriverService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = DriverRepository(session)
        self.usuarios = UserRepository(session)

    def get(self, driver_id: int) -> Driver:
        motorista = self.repo.get(driver_id)
        if motorista is None:
            raise NotFoundError("Motorista nao encontrado.")
        return motorista

    def listar(self, **filtros) -> list[Driver]:
        return self.repo.listar(**filtros)

    def criar(self, payload: DriverCreate) -> Driver:
        dados = payload.model_dump()
        if dados.get("user_id") is not None:
            self._validar_usuario(dados["user_id"])

        motorista = self.repo.add(Driver(**dados))
        self.session.commit()
        logger.info("Motorista %s criado (usuario=%s).", motorista.id, motorista.user_id)
        return motorista

    def atualizar(self, driver_id: int, payload: DriverUpdate) -> Driver:
        motorista = self.get(driver_id)
        dados = payload.model_dump(exclude_unset=True)

        trocou_usuario = (
            "user_id" in dados
            and dados["user_id"] != motorista.user_id
            and dados["user_id"] is not None
        )
        if trocou_usuario:
            self._validar_usuario(dados["user_id"], excluir_driver_id=motorista.id)

        _aplicar(motorista, dados)
        self.session.commit()
        return motorista

    def _validar_usuario(self, user_id: int, *, excluir_driver_id: int | None = None) -> None:
        usuario = self.usuarios.get_by_id(user_id)
        if usuario is None:
            raise NotFoundError("O usuario informado nao existe.")

        # Vincular um ADMIN a um perfil de motorista e erro de categoria: ele
        # passaria a aparecer na lista de quem pode receber rota.
        if usuario.role != Role.MOTORISTA.value:
            raise ValidationError(
                "So e possivel vincular um usuario com perfil de motorista. "
                f"{usuario.name} e administrador."
            )

        existente = self.repo.por_usuario(user_id)
        if existente is not None and existente.id != excluir_driver_id:
            raise ConflictError(
                f"O acesso de {usuario.name} ja esta vinculado ao motorista {existente.name}."
            )


# --------------------------------------------------------------------------- #
# Clientes
# --------------------------------------------------------------------------- #
class CustomerService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = CustomerRepository(session)

    def get(self, customer_id: int) -> Customer:
        cliente = self.repo.get(customer_id)
        if cliente is None:
            raise NotFoundError("Cliente nao encontrado.")
        return cliente

    def listar(self, **filtros) -> list[Customer]:
        return self.repo.listar(**filtros)

    def criar(self, payload: CustomerCreate) -> Customer:
        dados = payload.model_dump()
        origem = tirar_origem(self.session, dados)
        self._garantir_documento_livre(dados.get("document"))

        cliente = Customer(**dados)
        _reavaliar_geocodificacao(cliente, dados, origem)

        self.repo.add(cliente)
        self.session.commit()
        logger.info("Cliente %s criado.", cliente.id)
        return cliente

    def atualizar(self, customer_id: int, payload: CustomerUpdate) -> Customer:
        cliente = self.get(customer_id)
        dados = payload.model_dump(exclude_unset=True)
        origem = tirar_origem(self.session, dados)

        if "document" in dados and dados["document"] != cliente.document:
            self._garantir_documento_livre(dados["document"], excluir_id=cliente.id)

        _aplicar(cliente, dados)
        _reavaliar_geocodificacao(cliente, dados, origem)

        self.session.commit()
        return cliente

    def _garantir_documento_livre(
        self, documento: str | None, *, excluir_id: int | None = None
    ) -> None:
        # Sem documento nao ha o que conferir: varios clientes podem ficar
        # sem CPF/CNPJ, e o indice no banco e parcial justamente por isso.
        if not documento:
            return
        if self.repo.existe_campo("document", documento, excluir_id=excluir_id):
            raise ConflictError(f"Ja existe um cliente com o documento {documento}.")
