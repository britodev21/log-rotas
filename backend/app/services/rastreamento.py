"""Rastreamento ao vivo, previsão de chegada e navegação do motorista.

Três perguntas, uma por parte deste módulo:

1. ONDE ESTÁ o caminhão? — posições enviadas pelo celular do motorista.
2. QUANDO CHEGA em cada parada? — a partir da posição real, não do plano.
3. POR ONDE VAI? — a rota até a próxima parada, com as manobras.

Limite que molda tudo: o GPS vem de uma página web. O navegador só entrega
posição com a página em primeiro plano e a tela acesa. Por isso a navegação
é feita dentro do app — com o Google Maps na frente, a página ia para
segundo plano e o rastreamento parava. Mesmo assim ele pode parar (ligação,
troca de app, tela bloqueada), e o sistema DIZ quando parou em vez de
continuar mostrando o caminhão onde ele estava há dez minutos.

Privacidade: posição só é aceita com a rota INICIADA. Fora do expediente —
antes de sair da base ou depois de finalizar — o servidor descarta.
"""

from __future__ import annotations

import logging
import math
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import RouteStatus, StopStatus, StopType
from app.models.route import Route, RouteStop
from app.models.route_position import RoutePosition
from app.repositories.company_settings_repository import CompanySettingsRepository
from app.routing import navegacao as nav
from app.routing import transito

logger = logging.getLogger(__name__)

#: Sem ponto novo há mais que isto, o painel mostra "sem sinal". O celular
#: manda a cada ~10 s; 90 s tolera um trecho sem cobertura sem alarme falso.
SEM_SINAL_S = 90
#: Abaixo disto o caminhão está parado (3,6 km/h: anda em fila, mas não
#: está indo a lugar nenhum).
PARADO_MPS = 1.0
#: GPS pior que isto não diz onde o caminhão está: é o celular dentro do
#: galpão ou usando só a torre de celular.
PRECISAO_MAXIMA_M = 150.0
#: Relógio do celular adiantado além disto: o ponto é descartado.
FUTURO_TOLERADO_S = 120
MAXIMO_POR_ENVIO = 200
#: Quanto do trajeto recente o painel desenha atrás do caminhão.
RASTRO_MIN = 30
RASTRO_MAXIMO_PONTOS = 240

#: A previsão é recalculada no máximo a cada RECALCULO_S, e só se o caminhão
#: se mexeu ou alguma parada mudou; a cada RECALCULO_FORCADO_S, sempre.
#: Recalcular a cada consulta do painel (5 s) martelaria o OSRM público.
RECALCULO_S = 45
RECALCULO_FORCADO_S = 300
DESLOCAMENTO_RECALCULO_M = 150

ESTADOS_ABERTOS = (StopStatus.PENDENTE.value, StopStatus.CHEGOU.value)


def _agora() -> datetime:
    return datetime.now(UTC)


def metros(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6_371_000 * math.asin(math.sqrt(h))


# --------------------------------------------------------------------------- #
# Estruturas
# --------------------------------------------------------------------------- #
@dataclass
class PosicaoRecebida:
    latitude: float
    longitude: float
    registrada_em: datetime
    precisao_m: float | None = None
    velocidade_mps: float | None = None
    direcao_graus: float | None = None


@dataclass
class ResultadoEnvio:
    aceitas: int = 0
    descartadas: int = 0
    motivos: dict[str, int] = field(default_factory=dict)

    def descartar(self, motivo: str, quantas: int = 1) -> None:
        self.descartadas += quantas
        self.motivos[motivo] = self.motivos.get(motivo, 0) + quantas


@dataclass
class PrevisaoParada:
    stop_id: int
    sequencia: int
    tipo: str
    rotulo: str | None
    status: str
    chegada_prevista: datetime | None
    chegada_planejada: datetime | None
    #: Positivo: atrasado em relação ao plano. Negativo: adiantado.
    atraso_s: int | None
    #: Chega antes da janela do cliente e precisa esperar.
    espera_s: int = 0
    chegou_em: datetime | None = None


@dataclass
class Previsao:
    paradas: list[PrevisaoParada]
    termino_previsto: datetime | None
    #: De onde veio o tempo de deslocamento.
    fonte: str
    com_transito: bool
    #: Verdadeiro quando o deslocamento é linha reta ou só o plano.
    estimada: bool
    calculada_em: datetime
    posicao_de: datetime | None
    aviso: str | None = None

    @property
    def proxima(self) -> PrevisaoParada | None:
        return next(
            (p for p in self.paradas if p.status == StopStatus.PENDENTE.value), None
        )


# --------------------------------------------------------------------------- #
# Cálculo da previsão — puro, para ser testável sem banco e sem rede
# --------------------------------------------------------------------------- #
def _inicio_da_janela(parada: RouteStop, fuso: ZoneInfo, dia: date) -> datetime | None:
    """A janela da parada é a mais restritiva entre as entregas abertas nela."""
    inicios = [
        item.delivery.time_window_start
        for item in parada.items
        if item.delivery is not None and item.delivery.time_window_start is not None
    ]
    if not inicios:
        return None
    return datetime.combine(dia, max(inicios), tzinfo=fuso).astimezone(UTC)


def calcular_previsao(
    rota: Route,
    posicao: tuple[float, float] | None,
    *,
    agora: datetime,
    servico_padrao_s: int,
    rotear: Callable[[list[tuple[float, float]]], nav.RotaNavegavel],
    chegada: Callable[[RouteStop], tuple[float, float]],
    fator_transito: float | None = None,
    posicao_de: datetime | None = None,
) -> Previsao:
    """Hora prevista de chegada em cada parada que falta.

    Soma, em ordem: o deslocamento (pela rua, corrigido pelo trânsito quando
    houver), a espera pela janela do cliente e o tempo de serviço de cada
    parada. Se o motorista está numa parada agora, desconta o tempo que ele
    já passou lá.
    """
    fuso = ZoneInfo(get_settings().default_timezone)
    paradas = sorted(rota.stops, key=lambda s: s.sequence)
    abertas = [
        s
        for s in paradas
        if s.stop_type != StopType.BASE_SAIDA.value and s.status in ESTADOS_ABERTOS
    ]
    feitas = [
        PrevisaoParada(
            stop_id=s.id,
            sequencia=s.sequence,
            tipo=s.stop_type,
            rotulo=s.label,
            status=s.status,
            chegada_prevista=s.arrived_at,
            chegada_planejada=s.estimated_arrival,
            atraso_s=_atraso(s.arrived_at, s.estimated_arrival),
            chegou_em=s.arrived_at,
        )
        for s in paradas
        if s.stop_type != StopType.BASE_SAIDA.value and s.status not in ESTADOS_ABERTOS
    ]

    if not abertas:
        return Previsao(feitas, None, "CONCLUIDA", False, False, agora, posicao_de)

    resultado: list[PrevisaoParada] = []
    relogio = agora
    origem = posicao
    pendentes = abertas

    # Motorista parado numa entrega: a chegada já aconteceu; falta o serviço.
    primeira = abertas[0]
    if primeira.status == StopStatus.CHEGOU.value:
        servico = primeira.service_time_s or servico_padrao_s
        ja_passou = (agora - primeira.arrived_at).total_seconds() if primeira.arrived_at else 0
        relogio = agora + timedelta(seconds=max(0.0, servico - ja_passou))
        origem = chegada(primeira)
        pendentes = abertas[1:]
        resultado.append(
            PrevisaoParada(
                stop_id=primeira.id,
                sequencia=primeira.sequence,
                tipo=primeira.stop_type,
                rotulo=primeira.label,
                status=primeira.status,
                chegada_prevista=primeira.arrived_at,
                chegada_planejada=primeira.estimated_arrival,
                atraso_s=_atraso(primeira.arrived_at, primeira.estimated_arrival),
                chegou_em=primeira.arrived_at,
            )
        )

    if origem is None:
        # Sem nenhuma posição: não há de onde calcular. Devolve o plano, e
        # diz que é o plano.
        for s in pendentes:
            resultado.append(
                PrevisaoParada(
                    stop_id=s.id,
                    sequencia=s.sequence,
                    tipo=s.stop_type,
                    rotulo=s.label,
                    status=s.status,
                    chegada_prevista=s.estimated_arrival,
                    chegada_planejada=s.estimated_arrival,
                    atraso_s=None,
                )
            )
        termino = resultado[-1].chegada_prevista if resultado else None
        return Previsao(
            feitas + resultado,
            termino,
            "PLANEJADO",
            False,
            True,
            agora,
            None,
            "Ainda não chegou nenhuma posição do celular do motorista. Os horários "
            "são os do planejamento, não uma previsão.",
        )

    trajeto = rotear([origem, *[chegada(s) for s in pendentes]]) if pendentes else None
    multiplicador = fator_transito or 1.0

    for s, perna in zip(pendentes, trajeto.pernas if trajeto else [], strict=False):
        relogio = relogio + timedelta(seconds=perna.duracao_s * multiplicador)
        chegada_prevista = relogio
        espera = 0
        e_entrega = s.stop_type == StopType.ENTREGA.value
        janela = _inicio_da_janela(s, fuso, rota.date) if e_entrega else None
        if janela and chegada_prevista < janela:
            espera = int((janela - chegada_prevista).total_seconds())
        servico = (s.service_time_s or servico_padrao_s) if e_entrega else 0
        relogio = chegada_prevista + timedelta(seconds=espera + servico)
        resultado.append(
            PrevisaoParada(
                stop_id=s.id,
                sequencia=s.sequence,
                tipo=s.stop_type,
                rotulo=s.label,
                status=s.status,
                chegada_prevista=chegada_prevista,
                chegada_planejada=s.estimated_arrival,
                atraso_s=_atraso(chegada_prevista, s.estimated_arrival),
                espera_s=espera,
            )
        )

    estimada = bool(trajeto and trajeto.estimada)
    if estimada:
        fonte = "HAVERSINE"
    elif fator_transito:
        fonte = "OSRM+TRANSITO"
    else:
        fonte = "OSRM"

    aviso = trajeto.aviso if trajeto else None
    if not fator_transito and not estimada:
        aviso = "Sem trânsito: os tempos consideram a rua livre."

    retorno = next((p for p in resultado if p.tipo == StopType.BASE_RETORNO.value), None)
    return Previsao(
        paradas=feitas + resultado,
        termino_previsto=retorno.chegada_prevista if retorno else relogio,
        fonte=fonte,
        com_transito=bool(fator_transito),
        estimada=estimada,
        calculada_em=agora,
        posicao_de=posicao_de,
        aviso=aviso,
    )


def _atraso(real: datetime | None, planejado: datetime | None) -> int | None:
    if real is None or planejado is None:
        return None
    return int((real - planejado).total_seconds())


# --------------------------------------------------------------------------- #
# Caches de processo
# --------------------------------------------------------------------------- #
@dataclass
class _Guardada:
    quando: datetime
    posicao: tuple[float, float] | None
    estado: str
    previsao: Previsao


_previsoes: dict[int, _Guardada] = {}
_fatores: dict[int, tuple[datetime, float | None]] = {}
_trava = threading.Lock()


def _estado_das_paradas(rota: Route) -> str:
    return "|".join(f"{s.id}:{s.status}" for s in sorted(rota.stops, key=lambda s: s.sequence))


def limpar_caches() -> None:
    """Para os testes: cada um começa sem previsão guardada."""
    with _trava:
        _previsoes.clear()
        _fatores.clear()


# --------------------------------------------------------------------------- #
# Serviço
# --------------------------------------------------------------------------- #
class RastreamentoService:
    def __init__(self, session: Session) -> None:
        self.session = session

    # ---------------------------------------------------------- posições
    def registrar(self, rota: Route, posicoes: list[PosicaoRecebida]) -> ResultadoEnvio:
        """Grava as posições válidas e conta as descartadas, com o motivo.

        Nunca levanta erro por posição ruim: o celular manda em lote, muitas
        vezes depois de um trecho sem sinal, e um ponto estranho não pode
        custar os outros.
        """
        resultado = ResultadoEnvio()

        if rota.status != RouteStatus.INICIADA.value:
            # Privacidade: fora da execução da rota, a posição do motorista
            # não é assunto do sistema.
            resultado.descartar("rota não está em andamento", len(posicoes))
            return resultado

        agora = _agora()
        inicio = (rota.started_at or agora) - timedelta(minutes=1)

        for p in posicoes[:MAXIMO_POR_ENVIO]:
            if p.precisao_m is not None and p.precisao_m > PRECISAO_MAXIMA_M:
                resultado.descartar("GPS impreciso")
                continue
            quando = p.registrada_em
            if quando.tzinfo is None:
                quando = quando.replace(tzinfo=UTC)
            if quando > agora + timedelta(seconds=FUTURO_TOLERADO_S):
                resultado.descartar("relógio do celular adiantado")
                continue
            if quando < inicio:
                resultado.descartar("anterior ao início da rota")
                continue
            direcao = p.direcao_graus % 360 if p.direcao_graus is not None else None
            self.session.add(
                RoutePosition(
                    route_id=rota.id,
                    latitude=round(p.latitude, 6),
                    longitude=round(p.longitude, 6),
                    accuracy_m=round(p.precisao_m, 1) if p.precisao_m is not None else None,
                    speed_mps=round(max(0.0, p.velocidade_mps), 2)
                    if p.velocidade_mps is not None
                    else None,
                    heading_deg=round(direcao, 1) if direcao is not None else None,
                    recorded_at=quando,
                )
            )
            resultado.aceitas += 1

        if len(posicoes) > MAXIMO_POR_ENVIO:
            resultado.descartar("envio grande demais", len(posicoes) - MAXIMO_POR_ENVIO)

        self.session.commit()
        return resultado

    def ultima(self, route_id: int) -> RoutePosition | None:
        return self.session.scalars(
            select(RoutePosition)
            .where(RoutePosition.route_id == route_id)
            .order_by(RoutePosition.recorded_at.desc())
            .limit(1)
        ).first()

    def rastro(self, route_id: int, *, minutos: int = RASTRO_MIN) -> list[RoutePosition]:
        desde = _agora() - timedelta(minutes=minutos)
        pontos = list(
            self.session.scalars(
                select(RoutePosition)
                .where(RoutePosition.route_id == route_id, RoutePosition.recorded_at >= desde)
                .order_by(RoutePosition.recorded_at)
            )
        )
        if len(pontos) <= RASTRO_MAXIMO_PONTOS:
            return pontos
        # Afina mantendo o último: é ele que encosta no marcador do caminhão.
        passo = math.ceil(len(pontos) / RASTRO_MAXIMO_PONTOS)
        return [*pontos[:-1:passo], pontos[-1]]

    # --------------------------------------------------------- previsão
    def _servico_padrao_s(self) -> int:
        config = CompanySettingsRepository(self.session).get()
        return (config.default_stop_service_minutes if config else 60) * 60

    @staticmethod
    def chegada(parada: RouteStop) -> tuple[float, float]:
        return nav.ponto_de_chegada(
            float(parada.latitude), float(parada.longitude), parada.address
        )

    def _fator_transito(
        self, rota: Route, pontos: list[tuple[float, float]], osrm_s: int
    ) -> float | None:
        """Fator de trânsito da rota, consultando o Google no máximo a cada
        `traffic_refresh_s`. None quando não há trânsito configurado ou o
        Google recusou — e a previsão diz "sem trânsito"."""
        if not transito.disponivel() or len(pontos) < 2:
            return None
        agora = _agora()
        guardado = _fatores.get(rota.id)
        intervalo = get_settings().traffic_refresh_s
        if guardado and (agora - guardado[0]).total_seconds() < intervalo:
            return guardado[1]
        try:
            tempo = transito.consultar(pontos)
        except transito.TransitoIndisponivel as exc:
            logger.info("Previsão sem trânsito na rota %s: %s", rota.id, exc)
            # Guarda a falha pelo mesmo intervalo: repetir a chamada recusada
            # a cada recálculo só custaria latência.
            _fatores[rota.id] = (agora, None)
            return None
        valor = transito.fator(tempo.total_s, osrm_s)
        _fatores[rota.id] = (agora, valor)
        return valor

    def previsao(self, rota: Route, ultima: RoutePosition | None = None) -> Previsao:
        ultima = ultima if ultima is not None else self.ultima(rota.id)
        posicao = (float(ultima.latitude), float(ultima.longitude)) if ultima else None
        agora = _agora()
        estado = _estado_das_paradas(rota)

        guardada = _previsoes.get(rota.id)
        if guardada and guardada.estado == estado:
            idade = (agora - guardada.quando).total_seconds()
            mexeu = (
                posicao is not None
                and guardada.posicao is not None
                and metros(posicao, guardada.posicao) >= DESLOCAMENTO_RECALCULO_M
            ) or (posicao is None) != (guardada.posicao is None)
            if idade < RECALCULO_S or (idade < RECALCULO_FORCADO_S and not mexeu):
                return guardada.previsao

        # A rota pela rua e calculada uma vez; o fator de transito, que
        # depende dela, sai junto. A previsao entao usa os dois.
        trajetos: dict[tuple, nav.RotaNavegavel] = {}
        fatores: dict[tuple, float | None] = {}

        def rotear(pontos: list[tuple[float, float]]) -> nav.RotaNavegavel:
            chave = tuple(pontos)
            if chave not in trajetos:
                trajeto = nav.rota(pontos)
                trajetos[chave] = trajeto
                fatores[chave] = (
                    None
                    if trajeto.estimada
                    else self._fator_transito(rota, pontos, trajeto.duracao_s)
                )
            return trajetos[chave]

        comum = dict(
            agora=agora,
            servico_padrao_s=self._servico_padrao_s(),
            rotear=rotear,
            chegada=self.chegada,
            posicao_de=ultima.recorded_at if ultima else None,
        )
        resultado = calcular_previsao(rota, posicao, **comum)
        fator = next((v for v in fatores.values() if v), None)
        if fator:
            resultado = calcular_previsao(rota, posicao, fator_transito=fator, **comum)

        with _trava:
            _previsoes[rota.id] = _Guardada(agora, posicao, estado, resultado)
        return resultado

    # ------------------------------------------------------------ painel
    @staticmethod
    def situacao(rota: Route, ultima: RoutePosition | None, agora: datetime) -> str:
        if ultima is None:
            return "SEM_POSICAO"
        if (agora - ultima.received_at).total_seconds() > SEM_SINAL_S:
            return "SEM_SINAL"
        if any(s.status == StopStatus.CHEGOU.value for s in rota.stops):
            return "NA_PARADA"
        if ultima.speed_mps is not None and float(ultima.speed_mps) < PARADO_MPS:
            return "PARADO"
        return "EM_MOVIMENTO"

    def rotas_em_andamento(self, dia: date | None = None) -> list[Route]:
        alvo = dia or datetime.now(ZoneInfo(get_settings().default_timezone)).date()
        return list(
            self.session.scalars(
                select(Route)
                .where(Route.date == alvo, Route.status == RouteStatus.INICIADA.value)
                .order_by(Route.id)
            ).unique()
        )

    # --------------------------------------------------------- navegação
    @staticmethod
    def proxima_parada(rota: Route) -> RouteStop | None:
        for s in sorted(rota.stops, key=lambda s: s.sequence):
            if s.stop_type == StopType.BASE_SAIDA.value:
                continue
            if s.status in ESTADOS_ABERTOS:
                return s
        return None

    def navegar(self, rota: Route, origem: tuple[float, float]) -> dict:
        """Rota da posição atual até a próxima parada, com as manobras."""
        parada = self.proxima_parada(rota)
        if parada is None:
            return {"concluida": True, "parada": None}

        destino = self.chegada(parada)
        trajeto = nav.rota([origem, destino], manobras=True)
        fator = None
        if not trajeto.estimada:
            fator = self._fator_transito(rota, [origem, destino], trajeto.duracao_s)
        duracao = round(trajeto.duracao_s * (fator or 1.0))
        return {
            "concluida": False,
            "parada": parada,
            "ponto_chegada": destino,
            "trajeto": trajeto,
            "duracao_s": duracao,
            "chegada_prevista": _agora() + timedelta(seconds=duracao),
            "com_transito": bool(fator),
        }
