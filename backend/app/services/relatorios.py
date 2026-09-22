"""Relatórios: o que foi prometido, o que aconteceu, e a diferença.

Três perguntas, nesta ordem de importância para quem toca a operação:

1. **O que saiu e o que não saiu**, com o motivo de cada insucesso. É o que
   responde reclamação de cliente e mostra onde a operação perde entrega.
2. **Os horários foram cumpridos?** Atraso é `arrived_at` menos
   `estimated_arrival`, parada por parada. Sem isso, "o cliente reclamou de
   atraso" é palavra contra palavra.
3. **Os tempos planejados batem com a realidade?** Duas medições:
   - o tempo parado na entrega (`departed_at - arrived_at`) contra o
     planejado (`service_time_s`, 60 min por padrão);
   - o tempo de deslocamento entre paradas contra o previsto, separado por
     fonte da matriz — é assim que se vê se o trânsito do Google acertou
     mais que a rua livre do OSRM.

A terceira é a que melhora o planejamento do mês que vem: enquanto o tempo
de serviço for um palpite de 60 minutos, todo horário previsto carrega esse
palpite. O relatório transforma o palpite em número medido — e diz de
quantas paradas ele saiu, porque média de três entregas não é calibração.

Nada aqui inventa dado: parada sem registro de chegada não entra na conta de
pontualidade, e cada bloco devolve o tamanho da amostra.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date

from sqlalchemy import Float, and_, case, cast, func, literal_column, select
from sqlalchemy.orm import Session

from app.core.enums import DeliveryStatus, StopStatus, StopType
from app.models.driver import Driver
from app.models.route import Route, RoutePlan, RouteStop, RouteStopDelivery
from app.models.vehicle import Vehicle

#: Tolerância para "chegou no horário": 15 min para cada lado. Mais apertado
#: que isso julgaria o trânsito, não a operação.
TOLERANCIA_S = 15 * 60
#: Acima disto o atraso deixa de ser desvio e vira problema do dia.
ATRASO_GRAVE_S = 60 * 60
#: Abaixo deste número de paradas, a média não calibra nada — a tela diz.
AMOSTRA_MINIMA = 20
#: Registro de chegada e de saída no mesmo minuto não é uma entrega de um
#: minuto: é o motorista marcando tudo de uma vez, no fim. Entra na conta e
#: a mediana do tempo de parada despenca. Fica de fora, e a tela diz quantos.
REGISTRO_EM_BLOCO_S = 60


@dataclass(frozen=True)
class Periodo:
    de: date
    ate: date


def _segundos(intervalo):
    """Intervalo do Postgres em segundos, como número."""
    return func.extract("epoch", intervalo)


def _paradas_de_entrega(periodo: Periodo, motorista_id: int | None):
    """Paradas de entrega das rotas do período."""
    condicoes = [
        Route.date >= periodo.de,
        Route.date <= periodo.ate,
        RouteStop.stop_type == StopType.ENTREGA.value,
    ]
    if motorista_id:
        condicoes.append(Route.driver_id == motorista_id)
    return and_(*condicoes)


def entregas(session: Session, periodo: Periodo, motorista_id: int | None = None) -> dict:
    """Quantas saíram, quantas não, e por quê."""
    linha = session.execute(
        select(
            func.count().label("total"),
            func.count().filter(
                RouteStopDelivery.status == DeliveryStatus.ENTREGUE.value
            ).label("entregues"),
            func.count().filter(
                RouteStopDelivery.status == DeliveryStatus.NAO_ENTREGUE.value
            ).label("nao_entregues"),
            func.count().filter(
                RouteStopDelivery.status == DeliveryStatus.CANCELADA.value
            ).label("canceladas"),
        )
        .select_from(RouteStopDelivery)
        .join(RouteStop, RouteStop.id == RouteStopDelivery.route_stop_id)
        .join(Route, Route.id == RouteStop.route_id)
        .where(_paradas_de_entrega(periodo, motorista_id))
    ).one()

    motivos = session.execute(
        select(RouteStopDelivery.failure_reason, func.count().label("quantidade"))
        .join(RouteStop, RouteStop.id == RouteStopDelivery.route_stop_id)
        .join(Route, Route.id == RouteStop.route_id)
        .where(
            _paradas_de_entrega(periodo, motorista_id),
            RouteStopDelivery.status == DeliveryStatus.NAO_ENTREGUE.value,
        )
        .group_by(RouteStopDelivery.failure_reason)
        .order_by(func.count().desc())
    ).all()

    resolvidas = linha.entregues + linha.nao_entregues
    return {
        "total": linha.total,
        "entregues": linha.entregues,
        "nao_entregues": linha.nao_entregues,
        "canceladas": linha.canceladas,
        # Só entre as que tiveram desfecho: contar as que ainda estão em rota
        # como fracasso faria o número do dia piorar sozinho até a noite.
        "taxa_sucesso": round(linha.entregues / resolvidas, 4) if resolvidas else None,
        "motivos": [
            {"motivo": m or "NAO_INFORMADO", "quantidade": q} for m, q in motivos
        ],
    }


def rotas(session: Session, periodo: Periodo, motorista_id: int | None = None) -> dict:
    condicoes = [Route.date >= periodo.de, Route.date <= periodo.ate]
    if motorista_id:
        condicoes.append(Route.driver_id == motorista_id)

    # Só o que saiu da base. Rascunho nunca foi operação, e rota cancelada
    # (plano descartado) somaria quilometragem que nenhum caminhão rodou.
    saiu = Route.status.in_(["INICIADA", "FINALIZADA"])
    linha = session.execute(
        select(
            func.count().label("total"),
            func.count().filter(Route.status == "FINALIZADA").label("finalizadas"),
            func.coalesce(func.sum(Route.total_distance_m), 0).label("distancia_m"),
            func.coalesce(
                func.sum(_segundos(Route.finished_at - Route.started_at)), 0
            ).label("tempo_em_rota_s"),
        ).where(and_(*condicoes, saiu))
    ).one()

    viagens = session.scalar(
        select(func.count())
        .select_from(RouteStop)
        .join(Route, Route.id == RouteStop.route_id)
        .where(
            and_(*condicoes),
            saiu,
            RouteStop.stop_type == StopType.BASE_RECARGA.value,
        )
    )
    return {
        "total": linha.total,
        "finalizadas": linha.finalizadas,
        "distancia_m": int(linha.distancia_m),
        "tempo_em_rota_s": int(linha.tempo_em_rota_s or 0),
        # Uma saída por rota, mais uma por recarga.
        "viagens": linha.total + (viagens or 0),
    }


def pontualidade(session: Session, periodo: Periodo, motorista_id: int | None = None) -> dict:
    """Chegou quando o plano disse que chegaria?"""
    atraso = _segundos(RouteStop.arrived_at - RouteStop.estimated_arrival)
    linha = session.execute(
        select(
            func.count().label("paradas"),
            func.count().filter(atraso < -TOLERANCIA_S).label("adiantadas"),
            func.count()
            .filter(and_(atraso >= -TOLERANCIA_S, atraso <= TOLERANCIA_S))
            .label("no_horario"),
            func.count()
            .filter(and_(atraso > TOLERANCIA_S, atraso <= ATRASO_GRAVE_S))
            .label("atrasadas"),
            func.count().filter(atraso > ATRASO_GRAVE_S).label("muito_atrasadas"),
            func.avg(atraso).label("atraso_medio_s"),
            func.percentile_cont(0.5).within_group(atraso).label("atraso_mediano_s"),
        )
        .select_from(RouteStop)
        .join(Route, Route.id == RouteStop.route_id)
        .where(
            _paradas_de_entrega(periodo, motorista_id),
            RouteStop.arrived_at.is_not(None),
            RouteStop.estimated_arrival.is_not(None),
        )
    ).one()

    return {
        "paradas": linha.paradas,
        "adiantadas": linha.adiantadas,
        "no_horario": linha.no_horario,
        "atrasadas": linha.atrasadas,
        "muito_atrasadas": linha.muito_atrasadas,
        "atraso_medio_s": round(linha.atraso_medio_s) if linha.atraso_medio_s else None,
        "atraso_mediano_s": round(linha.atraso_mediano_s)
        if linha.atraso_mediano_s is not None
        else None,
        "tolerancia_s": TOLERANCIA_S,
    }


def tempo_de_parada(
    session: Session, periodo: Periodo, motorista_id: int | None = None
) -> dict:
    """O tempo planejado por entrega (60 min por padrão) está certo?"""
    real = _segundos(RouteStop.departed_at - RouteStop.arrived_at)
    base = (
        select(RouteStop, real.label("real_s"))
        .join(Route, Route.id == RouteStop.route_id)
        .where(
            _paradas_de_entrega(periodo, motorista_id),
            RouteStop.arrived_at.is_not(None),
            RouteStop.departed_at.is_not(None),
        )
        .subquery()
    )
    em_bloco = session.scalar(
        select(func.count()).select_from(base).where(base.c.real_s < REGISTRO_EM_BLOCO_S)
    )
    linha = session.execute(
        select(
            func.count().label("amostras"),
            func.avg(real).label("real_medio_s"),
            func.percentile_cont(0.5).within_group(real).label("real_mediano_s"),
            func.percentile_cont(0.9).within_group(real).label("real_p90_s"),
            func.avg(RouteStop.service_time_s).label("planejado_medio_s"),
        )
        .select_from(RouteStop)
        .join(Route, Route.id == RouteStop.route_id)
        .where(
            _paradas_de_entrega(periodo, motorista_id),
            RouteStop.arrived_at.is_not(None),
            RouteStop.departed_at.is_not(None),
            # Parada aberta de um dia para o outro é registro esquecido, não
            # entrega de seis horas; e tudo marcado no mesmo minuto é registro
            # em bloco, não entrega de um minuto. Nenhum dos dois calibra.
            real >= REGISTRO_EM_BLOCO_S,
            real < 6 * 3600,
        )
    ).one()

    return {
        "amostras": linha.amostras,
        "real_medio_s": round(linha.real_medio_s) if linha.real_medio_s else None,
        "real_mediano_s": round(linha.real_mediano_s)
        if linha.real_mediano_s is not None
        else None,
        "real_p90_s": round(linha.real_p90_s) if linha.real_p90_s is not None else None,
        "planejado_medio_s": round(linha.planejado_medio_s)
        if linha.planejado_medio_s
        else None,
        "amostra_minima": AMOSTRA_MINIMA,
        #: Paradas em que chegada e saída foram marcadas juntas.
        "registros_em_bloco": em_bloco or 0,
    }


def deslocamento(
    session: Session, periodo: Periodo, motorista_id: int | None = None
) -> list[dict]:
    """Tempo real entre paradas contra o previsto, por fonte da matriz.

    O real é a chegada na parada menos a saída da anterior — o que inclui o
    que o plano não previa (uma parada para abastecer, o cliente que não
    atende o portão). Por isso a comparação é de MEDIANA, não de média: um
    caso desses não pode mover o número que calibra o planejamento.
    """
    anterior = (
        select(
            RouteStop.id.label("stop_id"),
            func.lag(RouteStop.departed_at)
            .over(partition_by=RouteStop.route_id, order_by=RouteStop.sequence)
            .label("saida_anterior"),
        )
        .join(Route, Route.id == RouteStop.route_id)
        .where(
            Route.date >= periodo.de,
            Route.date <= periodo.ate,
            RouteStop.stop_type.in_(
                [StopType.ENTREGA.value, StopType.BASE_SAIDA.value, StopType.BASE_RECARGA.value]
            ),
        )
        .subquery()
    )

    real = _segundos(RouteStop.arrived_at - anterior.c.saida_anterior)
    condicoes = [
        _paradas_de_entrega(periodo, motorista_id),
        RouteStop.arrived_at.is_not(None),
        anterior.c.saida_anterior.is_not(None),
        RouteStop.duration_from_previous_s.is_not(None),
        RouteStop.duration_from_previous_s > 0,
        # Mesma razão do tempo de parada: saída e chegada no mesmo minuto é
        # registro em bloco, não um trecho percorrido em segundos.
        real >= REGISTRO_EM_BLOCO_S,
        real < 3 * 3600,
    ]

    linhas = session.execute(
        select(
            func.coalesce(RoutePlan.matrix_source, "DESCONHECIDA").label("fonte"),
            func.count().label("amostras"),
            func.percentile_cont(0.5)
            .within_group(cast(RouteStop.duration_from_previous_s, Float))
            .label("previsto_mediano_s"),
            func.percentile_cont(0.5).within_group(real).label("real_mediano_s"),
            func.percentile_cont(0.5)
            .within_group(real / cast(RouteStop.duration_from_previous_s, Float))
            .label("razao_mediana"),
        )
        .select_from(RouteStop)
        .join(Route, Route.id == RouteStop.route_id)
        # A fonte da matriz e do PLANO: a rota so aponta para ele. Rota
        # criada fora de um plano entra como DESCONHECIDA, nao some.
        .outerjoin(RoutePlan, RoutePlan.id == Route.route_plan_id)
        .join(anterior, anterior.c.stop_id == RouteStop.id)
        .where(*condicoes)
        .group_by(literal_column("1"))
        .order_by(func.count().desc())
    ).all()

    return [
        {
            "fonte": linha.fonte,
            "amostras": linha.amostras,
            "previsto_mediano_s": round(linha.previsto_mediano_s),
            "real_mediano_s": round(linha.real_mediano_s),
            "razao_mediana": round(linha.razao_mediana, 3),
        }
        for linha in linhas
    ]


def por_motorista(session: Session, periodo: Periodo) -> list[dict]:
    atraso = _segundos(RouteStop.arrived_at - RouteStop.estimated_arrival)
    linhas = session.execute(
        select(
            Driver.id,
            Driver.name,
            func.count(RouteStopDelivery.id).label("entregas"),
            func.count(RouteStopDelivery.id)
            .filter(RouteStopDelivery.status == DeliveryStatus.ENTREGUE.value)
            .label("entregues"),
            func.count(RouteStopDelivery.id)
            .filter(RouteStopDelivery.status == DeliveryStatus.NAO_ENTREGUE.value)
            .label("nao_entregues"),
            func.avg(
                case((RouteStop.arrived_at.is_not(None), atraso), else_=None)
            ).label("atraso_medio_s"),
        )
        .select_from(Route)
        .join(Driver, Driver.id == Route.driver_id)
        .join(RouteStop, RouteStop.route_id == Route.id)
        .join(RouteStopDelivery, RouteStopDelivery.route_stop_id == RouteStop.id)
        .where(_paradas_de_entrega(periodo, None))
        .group_by(Driver.id, Driver.name)
        .order_by(func.count(RouteStopDelivery.id).desc())
    ).all()

    return [
        {
            "id": linha.id,
            "nome": linha.name,
            "entregas": linha.entregas,
            "entregues": linha.entregues,
            "nao_entregues": linha.nao_entregues,
            "taxa_sucesso": round(linha.entregues / (linha.entregues + linha.nao_entregues), 4)
            if (linha.entregues + linha.nao_entregues)
            else None,
            "atraso_medio_s": round(linha.atraso_medio_s)
            if linha.atraso_medio_s is not None
            else None,
        }
        for linha in linhas
    ]


def por_dia(session: Session, periodo: Periodo, motorista_id: int | None = None) -> list[dict]:
    linhas = session.execute(
        select(
            Route.date,
            func.count(RouteStopDelivery.id)
            .filter(RouteStopDelivery.status == DeliveryStatus.ENTREGUE.value)
            .label("entregues"),
            func.count(RouteStopDelivery.id)
            .filter(RouteStopDelivery.status == DeliveryStatus.NAO_ENTREGUE.value)
            .label("nao_entregues"),
        )
        .select_from(Route)
        .join(RouteStop, RouteStop.route_id == Route.id)
        .join(RouteStopDelivery, RouteStopDelivery.route_stop_id == RouteStop.id)
        .where(_paradas_de_entrega(periodo, motorista_id))
        .group_by(Route.date)
        .order_by(Route.date)
    ).all()

    return [
        {
            "dia": linha.date.isoformat(),
            "entregues": linha.entregues,
            "nao_entregues": linha.nao_entregues,
        }
        for linha in linhas
    ]


def completo(session: Session, periodo: Periodo, motorista_id: int | None = None) -> dict:
    return {
        "de": periodo.de.isoformat(),
        "ate": periodo.ate.isoformat(),
        "motorista_id": motorista_id,
        "entregas": entregas(session, periodo, motorista_id),
        "rotas": rotas(session, periodo, motorista_id),
        "pontualidade": pontualidade(session, periodo, motorista_id),
        "tempo_de_parada": tempo_de_parada(session, periodo, motorista_id),
        "deslocamento": deslocamento(session, periodo, motorista_id),
        "por_motorista": por_motorista(session, periodo),
        "por_dia": por_dia(session, periodo, motorista_id),
    }


CABECALHO_CSV = [
    "data",
    "rota",
    "sequencia",
    "cliente",
    "endereco",
    "motorista",
    "veiculo",
    "viagem",
    "status",
    "motivo",
    "chegada_prevista",
    "chegada_real",
    "atraso_min",
    "saida_real",
    "minutos_na_parada",
    "recebedor",
    "observacao",
]


def csv_das_entregas(
    session: Session, periodo: Periodo, motorista_id: int | None = None
) -> str:
    """Uma linha por entrega, com o previsto e o realizado lado a lado.

    Existe porque relatório de logística sempre acaba numa planilha: o
    contador quer conferir, o cliente quer o comprovante de um dia, e a
    pessoa que toca a operação tem a própria forma de olhar os números.
    """
    linhas = session.execute(
        select(
            Route.date,
            Route.id.label("rota_id"),
            RouteStop.sequence,
            RouteStop.trip_number,
            RouteStop.label,
            RouteStop.address,
            Driver.name.label("motorista"),
            Vehicle.name.label("veiculo"),
            RouteStopDelivery.status,
            RouteStopDelivery.failure_reason,
            RouteStop.estimated_arrival,
            RouteStop.arrived_at,
            RouteStop.departed_at,
            RouteStopDelivery.receiver_name,
            RouteStopDelivery.notes,
        )
        .select_from(RouteStopDelivery)
        .join(RouteStop, RouteStop.id == RouteStopDelivery.route_stop_id)
        .join(Route, Route.id == RouteStop.route_id)
        .join(Vehicle, Vehicle.id == Route.vehicle_id)
        .outerjoin(Driver, Driver.id == Route.driver_id)
        .where(_paradas_de_entrega(periodo, motorista_id))
        .order_by(Route.date, Route.id, RouteStop.sequence)
    ).all()

    buffer = io.StringIO()
    # Ponto e vírgula e BOM: é assim que o Excel em português abre o arquivo
    # com as colunas separadas e os acentos certos, sem ninguém importar nada.
    escritor = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    escritor.writerow(CABECALHO_CSV)

    for linha in linhas:
        atraso = (
            round((linha.arrived_at - linha.estimated_arrival).total_seconds() / 60)
            if linha.arrived_at and linha.estimated_arrival
            else ""
        )
        na_parada = (
            round((linha.departed_at - linha.arrived_at).total_seconds() / 60)
            if linha.arrived_at and linha.departed_at
            else ""
        )
        escritor.writerow(
            [
                linha.date.isoformat(),
                linha.rota_id,
                linha.sequence,
                linha.label or "",
                linha.address or "",
                linha.motorista or "",
                linha.veiculo or "",
                linha.trip_number,
                linha.status,
                linha.failure_reason or "",
                _hora(linha.estimated_arrival),
                _hora(linha.arrived_at),
                atraso,
                _hora(linha.departed_at),
                na_parada,
                linha.receiver_name or "",
                (linha.notes or "").replace("\n", " "),
            ]
        )
    return "﻿" + buffer.getvalue()


def _hora(momento) -> str:
    """Hora local, como aparece na tela — não UTC, que ninguém confere."""
    if momento is None:
        return ""
    from zoneinfo import ZoneInfo

    from app.core.config import get_settings

    return momento.astimezone(ZoneInfo(get_settings().default_timezone)).strftime(
        "%d/%m/%Y %H:%M"
    )


def paradas_sem_registro(
    session: Session, periodo: Periodo, motorista_id: int | None = None
) -> int:
    """Paradas concluídas sem hora de chegada — o buraco da amostra.

    Aparece na tela ao lado dos números: uma pontualidade calculada sobre
    metade das paradas precisa dizer que é sobre metade.
    """
    return session.scalar(
        select(func.count())
        .select_from(RouteStop)
        .join(Route, Route.id == RouteStop.route_id)
        .where(
            _paradas_de_entrega(periodo, motorista_id),
            RouteStop.status == StopStatus.CONCLUIDA.value,
            RouteStop.arrived_at.is_(None),
        )
    )
