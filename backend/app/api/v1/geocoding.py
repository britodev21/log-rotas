"""Geocodificação e fila de revisão de endereços."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import or_, select

from app.api.deps import AdminUser, DbSession
from app.core.enums import GeocodeStatus
from app.geocoding import cep as cep_service
from app.geocoding import places
from app.geocoding.service import ALVOS, GeocodingService, guardar_lugar
from app.models.base_location import BaseLocation
from app.models.customer import Customer
from app.models.delivery import Delivery
from app.schemas.geocoding import (
    BuscaResultado,
    CandidatoRead,
    CoordenadaManual,
    EnderecoCepRead,
    GeocodeTentativaRead,
    LoteRequest,
    LoteResultado,
    LugarRead,
    PendenteRead,
    RecursosRead,
    SugestaoRead,
)
from app.services import precisao
from app.services.delivery_service import DeliveryService

router = APIRouter(prefix="/geocodificacao", tags=["Geocodificacao"])

#: Situações que exigem intervenção humana. `PENDENTE` entra porque, sem
#: coordenada, a entrega não pode ser planejada — e o administrador precisa
#: saber disso antes de tentar montar a rota, não durante.
#: Estados que o processamento em lote tenta resolver automaticamente.
#: Diferente do que a FILA mostra: a fila lista tudo que nao esta confiavel
#: (ver precisao.filtro_sql), inclusive OK com precisao de rua, que o lote
#: nao adianta reprocessar — o provedor devolveria a mesma rua de novo.
PRECISAM_ATENCAO = [
    GeocodeStatus.PENDENTE.value,
    GeocodeStatus.AMBIGUO.value,
    GeocodeStatus.FALHOU.value,
]


@router.get(
    "/pendentes",
    response_model=list[PendenteRead],
    summary="Endereços que precisam de atenção",
)
def pendentes(
    session: DbSession,
    _: AdminUser,
    tipo: Annotated[str | None, Query(description="entrega, cliente ou base.")] = None,
    limite: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[PendenteRead]:
    """Fila de revisão de endereços.

    Reúne tudo que não tem coordenada confiável — a mesma regra que o
    planejamento aplica, vinda do mesmo lugar (`precisao.filtro_sql`).

    Inclui, de propósito, o registro que o provedor resolveu com status OK
    mas só no nível da rua. Em Campo Grande esse é o caso comum, não a
    exceção: o OpenStreetMap tem número de porta em cerca de 530 prédios da
    cidade. Um pino desses aponta para um lugar qualquer da via, e a rota
    calculada em cima dele parece perfeita até o motorista chegar.

    A fila listava apenas PENDENTE, AMBIGUO e FALHOU, e esses registros não
    apareciam em tela nenhuma — o planejamento os recusava e não havia onde
    resolvê-los.
    """
    resultado: list[PendenteRead] = []

    consultas = {
        "entrega": (Delivery, lambda d: d.recipient_name or d.description or f"Entrega {d.id}"),
        "cliente": (Customer, lambda c: c.name),
        "base": (BaseLocation, lambda b: b.name),
    }

    for nome, (modelo, titulo) in consultas.items():
        if tipo and tipo != nome:
            continue

        stmt = (
            select(modelo)
            .where(
                precisao.filtro_sql(modelo),
                # Registro sem endereço nenhum não é problema de
                # geocodificação — é cadastro incompleto, e aparecer aqui
                # só poluiria a fila.
                or_(
                    modelo.address.is_not(None),
                    modelo.geocode_status != GeocodeStatus.PENDENTE.value,
                ),
            )
            .limit(limite)
        )

        for registro in session.scalars(stmt).unique():
            resultado.append(
                PendenteRead(
                    tipo=nome,
                    id=registro.id,
                    titulo=titulo(registro),
                    address=registro.address,
                    geocode_status=registro.geocode_status,
                    geocode_precision=registro.geocode_precision,
                    motivo=precisao.motivo(registro),
                    geocode_error=registro.geocode_error,
                    latitude=float(registro.latitude) if registro.latitude else None,
                    longitude=float(registro.longitude) if registro.longitude else None,
                )
            )

    return resultado


@router.post("/testar", response_model=GeocodeTentativaRead, summary="Testar um endereço")
def testar(
    endereco: Annotated[str, Query(min_length=3, max_length=255)],
    session: DbSession,
    _: AdminUser,
) -> GeocodeTentativaRead:
    """Consulta o provedor sem gravar em nenhum registro.

    Serve para conferir como o endereço será interpretado antes de cadastrar.
    """
    resultado = GeocodingService(session).geocodificar(endereco)
    session.commit()  # o cache foi alimentado
    return GeocodeTentativaRead(**resultado.__dict__)


@router.post("/lote", response_model=LoteResultado, summary="Geocodificar em lote")
def lote(payload: LoteRequest, session: DbSession, _: AdminUser) -> LoteResultado:
    """Processa uma fila de endereços pendentes.

    **Demora.** O Nominatim permite uma requisição por segundo, então 50
    endereços levam cerca de um minuto — endereços já vistos saem do cache e
    não contam. Um endereço que falha não interrompe os demais.
    """
    modelo = ALVOS[payload.tipo]

    if payload.tipo == "entrega":
        registros = DeliveryService(session).repo.para_geocodificar(payload.limite)
    else:
        estados = PRECISAM_ATENCAO if not payload.forcar else [*PRECISAM_ATENCAO, "OK"]
        stmt = (
            select(modelo)
            .where(modelo.address.is_not(None), modelo.geocode_status.in_(estados))
            .limit(payload.limite)
        )
        registros = list(session.scalars(stmt).unique())

    contagem = GeocodingService(session).geocodificar_lote(registros, forcar=payload.forcar)
    return LoteResultado(processados=len(registros), **contagem)


@router.get("/cep/{cep}", response_model=EnderecoCepRead, summary="Consultar um CEP")
def consultar_cep(
    cep: str,
    _: AdminUser,
    numero: Annotated[
        str | None, Query(max_length=20, description="Número, se já souber.")
    ] = None,
) -> EnderecoCepRead:
    """Busca logradouro, bairro, cidade e UF pelo CEP.

    Endereço brasileiro digitado por extenso é a pior entrada possível para
    geocodificação — "Av. Calógeras 1500" tem dezenas de grafias. CEP mais
    número acerta muito mais, e é por isso que o cadastro começa por aqui.

    Informando `numero`, a resposta já traz o endereço montado na ordem que
    o geocodificador espera.

    Responde **404** para CEP inexistente. O ViaCEP devolve 200 com
    `{"erro": true}` nesse caso — um status de sucesso carregando uma falha;
    tratar só o código HTTP faria o sistema aceitar um endereço vazio.
    """
    endereco = cep_service.consultar(cep)
    return EnderecoCepRead(
        cep=endereco.cep,
        cep_formatado=cep_service.formatar_cep(endereco.cep),
        logradouro=endereco.logradouro,
        bairro=endereco.bairro,
        cidade=endereco.cidade,
        uf=endereco.uf,
        endereco_montado=endereco.montar(numero),
        latitude=endereco.latitude,
        longitude=endereco.longitude,
    )


@router.get("/buscar", response_model=BuscaResultado, summary="Buscar um endereço")
def buscar(
    endereco: Annotated[str, Query(min_length=3, max_length=255)],
    session: DbSession,
    _: AdminUser,
) -> BuscaResultado:
    """Lista os lugares possíveis para um texto, com coordenada.

    Não decide nada: devolve os candidatos para a pessoa apontar no mapa e
    escolher. É o que permite buscar um endereço e ver **onde ele cai**
    antes de gravar.
    """
    servico = GeocodingService(session)
    candidatos = servico.provider.buscar(endereco)
    session.commit()  # a consulta alimentou o cache
    return BuscaResultado(
        consulta=endereco,
        candidatos=[
            CandidatoRead(
                latitude=c.latitude,
                longitude=c.longitude,
                display_name=c.display_name,
                precision=c.precision,
            )
            for c in candidatos
        ],
    )


@router.get("/recursos", response_model=RecursosRead, summary="O que esta ligado")
def recursos(_: AdminUser) -> RecursosRead:
    """Diz a tela se a busca do Google esta disponivel.

    Existe para a tela nao descobrir por tentativa: mostrar o campo do Google
    e trocar para o CEP no primeiro erro faria o formulario piscar.
    """
    return RecursosRead(autocomplete=places.disponivel())


@router.get("/sugestoes", response_model=list[SugestaoRead], summary="Sugestoes do Google")
def sugestoes(
    _: AdminUser,
    texto: Annotated[str, Query(min_length=3, max_length=200)],
    sessao: Annotated[str, Query(min_length=8, max_length=64)],
) -> list[SugestaoRead]:
    """Enderecos que existem, enquanto a pessoa digita.

    `sessao` e o token de sessao gerado no navegador: agrupa a digitacao e a
    escolha numa cobranca so. Sem ele o Google cobraria cada tecla.
    """
    return [SugestaoRead(**vars(s)) for s in places.sugerir(texto.strip(), sessao)]


@router.get("/lugar/{place_id}", response_model=LugarRead, summary="Detalhe do lugar escolhido")
def lugar(
    place_id: str,
    session: DbSession,
    _: AdminUser,
    sessao: Annotated[str | None, Query(max_length=64)] = None,
) -> LugarRead:
    """Endereco, componentes e ponto do lugar escolhido.

    Grava o resultado no cache: e contra ele que o servidor confere, na hora
    de salvar a entrega, se o ponto recebido e mesmo o que o Google devolveu
    — em vez de acreditar no navegador quando ele diz "e exato".
    """
    resultado = places.detalhar(place_id, sessao)
    guardar_lugar(session, resultado)
    session.commit()
    return LugarRead(
        place_id=resultado.place_id,
        endereco_formatado=resultado.endereco_formatado,
        latitude=resultado.latitude,
        longitude=resultado.longitude,
        precision=resultado.precision,
        tipo_ponto=resultado.tipo_ponto,
        logradouro=resultado.logradouro,
        numero=resultado.numero,
        bairro=resultado.bairro,
        cidade=resultado.cidade,
        uf=resultado.uf,
        cep=resultado.cep,
    )


# --------------------------------------------------------------------------- #
# ORDEM IMPORTA: as rotas de caminho fixo precisam vir ANTES das que usam
# parametro no lugar do primeiro segmento.
#
# `/geocodificacao/cep/79002000` (e `/geocodificacao/lugar/<id>`) casam com
# `/geocodificacao/{tipo}/{registro_id}`
# — com tipo="cep" e registro_id="79002000". Registrada primeiro, a rota
# generica faz o FastAPI achar o caminho, nao achar o metodo e responder 405,
# numa falha que nao parece ter relacao nenhuma com ordenacao.
# --------------------------------------------------------------------------- #


@router.post(
    "/{tipo}/{registro_id}",
    response_model=GeocodeTentativaRead,
    summary="Geocodificar um registro",
)
def geocodificar_um(
    tipo: str,
    registro_id: int,
    session: DbSession,
    _: AdminUser,
    forcar: Annotated[bool, Query(description="Sobrescreve pino manual.")] = False,
) -> GeocodeTentativaRead:
    """Pino ajustado à mão (`MANUAL`) não é sobrescrito sem `forcar=true`."""
    _, resultado = GeocodingService(session).geocodificar_um(tipo, registro_id, forcar=forcar)
    return GeocodeTentativaRead(**resultado.__dict__)


@router.put(
    "/{tipo}/{registro_id}/coordenada",
    response_model=GeocodeTentativaRead,
    summary="Definir a coordenada manualmente",
)
def definir_coordenada(
    tipo: str, registro_id: int, payload: CoordenadaManual, session: DbSession, _: AdminUser
) -> GeocodeTentativaRead:
    """Grava o pino arrastado no mapa.

    O registro passa a `MANUAL` e a geocodificação automática não o
    sobrescreve mais. É o que permite corrigir um endereço **uma vez** — o
    que importa em Campo Grande, onde loteamento novo e chácara têm
    cobertura irregular no OpenStreetMap.
    """
    registro = GeocodingService(session).definir_coordenada(
        tipo, registro_id, payload.latitude, payload.longitude
    )
    return GeocodeTentativaRead(
        status=registro.geocode_status,
        latitude=float(registro.latitude),
        longitude=float(registro.longitude),
        provider="manual",
    )
