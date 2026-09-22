"""Limpeza automática de dados antigos.

O que apaga, e por quê:

- POSIÇÕES DO GPS (padrão: 90 dias). É dado pessoal do motorista (LGPD):
  serve para acompanhar a rota e, por um tempo, para tirar dúvida sobre ela.
  Guardar para sempre seria guardar o trajeto diário de uma pessoa sem
  motivo. E é o dado que mais cresce: ~3.600 linhas por rota de 10 h.
- TENTATIVAS DE LOGIN (180 dias) e EVENTOS DE SEGURANÇA (730 dias):
  auditoria. Os eventos ficam mais, porque respondem perguntas que só
  aparecem muito depois ("quem promoveu este usuário a administrador?").
- CACHE DE ENDEREÇO QUE FALHOU (30 dias). Sem isto, um endereço que o
  provedor não achou em março nunca mais seria consultado — mesmo depois de
  o mapa daquela rua ser corrigido. O cache de sucesso fica.
- LUGARES DO GOOGLE GUARDADOS PARA CONFERÊNCIA (30 dias). Servem só no
  momento de salvar a entrega (o servidor confere que o ponto é o que o
  Google devolveu); depois disso não têm uso, e cresceriam a cada busca.
- TRECHOS COM TRÂNSITO de partidas que já passaram (1 dia). Servem para
  recalcular o plano do mesmo dia sem consultar o Google de novo; o trânsito
  previsto para uma terça que já passou não serve para nada.

Quando roda: todo dia, no horário `limpeza_hora` (padrão 3h de Campo
Grande), por um agendador dentro do próprio servidor — ver `Agendador`.
Também sob demanda, pela tela de Segurança ou por `python -m app.tarefas`.

Nunca roda em dobro: um bloqueio do PostgreSQL (advisory lock) garante que,
com vários processos, só um limpa por vez, e o registro em
`maintenance_runs` garante que a execução agendada acontece uma vez por dia.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import GeocodeStatus
from app.models.geocode_cache import GeocodeCache
from app.models.manutencao import MaintenanceRun
from app.models.route_position import RoutePosition
from app.models.seguranca import LoginAttempt, SecurityEvent
from app.models.trafego import TrafficLeg
from app.models.user import User

logger = logging.getLogger(__name__)

#: Número do bloqueio no PostgreSQL. Qualquer inteiro serve, desde que só a
#: limpeza o use.
CHAVE_DO_BLOQUEIO = 7_391_001
RETENCAO_CACHE_FALHAS_DIAS = 30

AGENDADA = "AGENDADA"
MANUAL = "MANUAL"


def limites(agora: datetime) -> dict[str, datetime]:
    c = get_settings()
    return {
        "posicoes": agora - timedelta(days=c.retencao_posicoes_dias),
        "tentativas_login": agora - timedelta(days=c.retencao_tentativas_login_dias),
        "eventos_seguranca": agora - timedelta(days=c.retencao_eventos_seguranca_dias),
        "cache_falhas": agora - timedelta(days=RETENCAO_CACHE_FALHAS_DIAS),
        "cache_transito": agora - timedelta(days=1),
    }


def limpar(
    session: Session,
    *,
    origem: str = AGENDADA,
    actor: User | None = None,
    agora: datetime | None = None,
) -> MaintenanceRun | None:
    """Apaga o que passou do prazo. None se outra limpeza estiver rodando.

    Uma transação só: o volume diário é pequeno (um dia de dados de cada
    tipo), e tudo-ou-nada é mais simples de entender do que meia limpeza.
    """
    agora = agora or datetime.now(UTC)

    # Bloqueio da TRANSAÇÃO: some sozinho no commit ou no rollback, então
    # uma limpeza que quebra no meio não deixa o bloqueio preso.
    if not session.scalar(
        text("SELECT pg_try_advisory_xact_lock(:chave)"), {"chave": CHAVE_DO_BLOQUEIO}
    ):
        logger.info("Limpeza ignorada: outra execucao esta em andamento.")
        return None

    # Conferido DEPOIS do bloqueio, e nao so antes: dois processos podiam
    # ver "hoje ainda nao rodou", o primeiro limpar e soltar o bloqueio, e o
    # segundo pega-lo em seguida e limpar de novo.
    if origem == AGENDADA:
        fuso = ZoneInfo(get_settings().default_timezone)
        if agendada_ja_rodou(session, agora.astimezone(fuso).date(), fuso):
            session.rollback()
            return None

    corte = limites(agora)
    try:
        resultado = {
            "posicoes": session.execute(
                delete(RoutePosition).where(RoutePosition.recorded_at < corte["posicoes"])
            ).rowcount,
            "tentativas_login": session.execute(
                delete(LoginAttempt).where(LoginAttempt.created_at < corte["tentativas_login"])
            ).rowcount,
            "eventos_seguranca": session.execute(
                delete(SecurityEvent).where(
                    SecurityEvent.created_at < corte["eventos_seguranca"]
                )
            ).rowcount,
            "cache_falhas": session.execute(
                delete(GeocodeCache).where(
                    GeocodeCache.status != GeocodeStatus.OK.value,
                    GeocodeCache.updated_at < corte["cache_falhas"],
                )
            ).rowcount,
            "cache_google": session.execute(
                delete(GeocodeCache).where(
                    GeocodeCache.normalized_address.like("place:%"),
                    GeocodeCache.updated_at < corte["cache_falhas"],
                )
            ).rowcount,
            "cache_transito": session.execute(
                delete(TrafficLeg).where(TrafficLeg.partida < corte["cache_transito"])
            ).rowcount,
        }
        execucao = MaintenanceRun(
            origem=origem,
            actor_id=actor.id if actor else None,
            iniciada_em=agora,
            terminada_em=datetime.now(UTC),
            resultado=resultado,
        )
        session.add(execucao)
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception("Falha na limpeza automatica")
        falha = MaintenanceRun(
            origem=origem,
            actor_id=actor.id if actor else None,
            iniciada_em=agora,
            terminada_em=datetime.now(UTC),
            erro=str(exc)[:500],
        )
        session.add(falha)
        session.commit()
        raise

    total = sum(resultado.values())
    logger.info("Limpeza %s concluida: %s linhas (%s).", origem.lower(), total, resultado)
    return execucao


def ultimas(session: Session, limite: int = 10) -> list[MaintenanceRun]:
    return list(
        session.scalars(
            select(MaintenanceRun).order_by(MaintenanceRun.iniciada_em.desc()).limit(limite)
        )
    )


def agendada_ja_rodou(session: Session, dia_local: date, fuso: ZoneInfo) -> bool:
    inicio = datetime.combine(dia_local, datetime.min.time(), tzinfo=fuso)
    return bool(
        session.scalar(
            select(func.count())
            .select_from(MaintenanceRun)
            .where(
                MaintenanceRun.origem == AGENDADA,
                MaintenanceRun.erro.is_(None),
                MaintenanceRun.iniciada_em >= inicio,
                MaintenanceRun.iniciada_em < inicio + timedelta(days=1),
            )
        )
    )


def deve_rodar(session: Session, agora_local: datetime) -> bool:
    """Chegou a hora e a limpeza de hoje ainda não aconteceu?

    "A partir da hora", e não "na hora": se o servidor estava desligado às
    3h, a limpeza roda assim que ele voltar, no mesmo dia — em vez de pular
    o dia.
    """
    hora = get_settings().limpeza_hora
    if hora < 0 or agora_local.hour < hora:
        return False
    return not agendada_ja_rodou(session, agora_local.date(), agora_local.tzinfo)


class Agendador(threading.Thread):
    """Confere a cada minuto se é hora de limpar.

    Uma thread dentro do servidor, e não um cron do sistema operacional:
    funciona igual no computador de desenvolvimento e no servidor, sem
    configuração a mais. Com vários processos, cada um tem o seu agendador —
    o bloqueio do PostgreSQL e o registro diário garantem uma limpeza só.
    """

    INTERVALO_S = 60

    def __init__(self, fabrica_de_sessao) -> None:
        super().__init__(name="agendador-limpeza", daemon=True)
        self.fabrica = fabrica_de_sessao
        self.parar = threading.Event()

    def run(self) -> None:
        while not self.parar.wait(self.INTERVALO_S):
            try:
                self.tique()
            except Exception:
                logger.exception("Falha no agendador de limpeza")

    def tique(self) -> None:
        fuso = ZoneInfo(get_settings().default_timezone)
        agora_local = datetime.now(fuso)
        with self.fabrica() as session:
            if deve_rodar(session, agora_local):
                limpar(session, origem=AGENDADA)
