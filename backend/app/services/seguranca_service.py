"""Bloqueio por tentativas de login e registro de eventos de segurança.

As regras, e o porquê de cada uma (docs/SEGURANCA.md tem a versão longa):

- Falhas da MESMA CONTA dentro da janela bloqueiam a conta; falhas do
  MESMO IP, em qualquer conta, bloqueiam o IP. As duas cobrem ataques
  diferentes: adivinhar a senha de uma pessoa, e testar uma senha comum em
  muitas contas.
- Vale para e-mail que não existe. Bloquear só conta existente revelaria,
  pelo comportamento, quais contas existem.
- Durante o bloqueio, nem a senha certa entra. Se entrasse, não seria
  bloqueio: o atacante só precisaria acertar dentro dele.
- Tentativa feita durante o bloqueio NÃO estende o bloqueio. Senão quem
  ataca manteria o dono da conta trancado para sempre, só insistindo.
- Login bem-sucedido zera a contagem da conta; o admin também pode zerar
  (desbloquear), e isso fica registrado.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.seguranca import LoginAttempt, SecurityEvent
from app.models.user import User

logger = logging.getLogger(__name__)

# Motivos de uma tentativa.
CREDENCIAL = "CREDENCIAL"
INATIVO = "INATIVO"
BLOQUEADO = "BLOQUEADO"
OK = "OK"
DESBLOQUEIO = "DESBLOQUEIO"

#: Só estes contam como falha para bloquear. BLOQUEADO não conta (ver o
#: cabeçalho do módulo); INATIVO conta, porque quem tenta entrar numa conta
#: desativada está, do ponto de vista do sistema, errando a credencial.
_CONTAM_COMO_FALHA = (CREDENCIAL, INATIVO)
#: Estes encerram a sequência de falhas de uma conta.
_ZERAM_A_CONTA = (OK, DESBLOQUEIO)


def normalizar_email(email: str) -> str:
    return (email or "").strip().lower()[:254]


@dataclass(frozen=True)
class Bloqueio:
    alvo: str  # "conta" ou "ip"
    ate: datetime

    def segundos_restantes(self, agora: datetime) -> int:
        return max(1, int((self.ate - agora).total_seconds()) + 1)


@dataclass(frozen=True)
class ContaBloqueada:
    email: str
    ate: datetime
    falhas: int


class SegurancaService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.config = get_settings()

    # ------------------------------------------------------------ janelas
    def _janela(self, agora: datetime) -> datetime:
        return agora - timedelta(minutes=self.config.login_janela_minutos)

    def _falhas_da_conta(self, email: str, agora: datetime) -> list[datetime]:
        desde = self._janela(agora)
        ultimo_zeramento = self.session.scalar(
            select(func.max(LoginAttempt.created_at)).where(
                LoginAttempt.email == email,
                LoginAttempt.motivo.in_(_ZERAM_A_CONTA),
                LoginAttempt.created_at >= desde,
            )
        )
        if ultimo_zeramento:
            desde = ultimo_zeramento
        return list(
            self.session.scalars(
                select(LoginAttempt.created_at)
                .where(
                    LoginAttempt.email == email,
                    LoginAttempt.motivo.in_(_CONTAM_COMO_FALHA),
                    LoginAttempt.created_at > desde,
                )
                .order_by(LoginAttempt.created_at)
            )
        )

    def _falhas_do_ip(self, ip: str, agora: datetime) -> list[datetime]:
        return list(
            self.session.scalars(
                select(LoginAttempt.created_at)
                .where(
                    LoginAttempt.ip == ip,
                    LoginAttempt.motivo.in_(_CONTAM_COMO_FALHA),
                    LoginAttempt.created_at >= self._janela(agora),
                )
                .order_by(LoginAttempt.created_at)
            )
        )

    def _bloqueio_por(self, falhas: list[datetime], limite: int) -> datetime | None:
        """Bloqueado até `bloqueio` minutos depois da falha que atingiu o limite."""
        if len(falhas) < limite:
            return None
        return falhas[limite - 1] + timedelta(minutes=self.config.login_bloqueio_minutos)

    # ------------------------------------------------------------- consulta
    def bloqueio(self, email: str, ip: str | None) -> Bloqueio | None:
        agora = datetime.now(UTC)
        email = normalizar_email(email)

        ate = self._bloqueio_por(
            self._falhas_da_conta(email, agora), self.config.login_max_falhas_conta
        )
        if ate and ate > agora:
            return Bloqueio("conta", ate)

        if ip:
            ate = self._bloqueio_por(
                self._falhas_do_ip(ip, agora), self.config.login_max_falhas_ip
            )
            if ate and ate > agora:
                return Bloqueio("ip", ate)
        return None

    def contas_bloqueadas(self) -> list[ContaBloqueada]:
        """Contas bloqueadas agora, para a tela do administrador."""
        agora = datetime.now(UTC)
        emails = self.session.scalars(
            select(LoginAttempt.email)
            .where(
                LoginAttempt.motivo.in_(_CONTAM_COMO_FALHA),
                LoginAttempt.created_at >= self._janela(agora)
                - timedelta(minutes=self.config.login_bloqueio_minutos),
            )
            .distinct()
        )
        bloqueadas = []
        for email in emails:
            falhas = self._falhas_da_conta(email, agora)
            ate = self._bloqueio_por(falhas, self.config.login_max_falhas_conta)
            if ate and ate > agora:
                bloqueadas.append(ContaBloqueada(email, ate, len(falhas)))
        return sorted(bloqueadas, key=lambda b: b.ate, reverse=True)

    # ------------------------------------------------------------- registro
    def registrar_tentativa(
        self,
        *,
        email: str,
        ip: str | None,
        motivo: str,
        user: User | None = None,
        user_agent: str | None = None,
    ) -> None:
        email = normalizar_email(email)
        self.session.add(
            LoginAttempt(
                email=email,
                ip=ip,
                sucesso=motivo == OK,
                motivo=motivo,
                user_id=user.id if user else None,
                user_agent=(user_agent or "")[:200] or None,
            )
        )
        self.session.flush()

        # A falha que ATINGE o limite vira evento: é o momento em que alguém
        # pode estar tentando adivinhar a senha, e o admin precisa ver isso.
        if motivo in _CONTAM_COMO_FALHA:
            agora = datetime.now(UTC)
            falhas = self._falhas_da_conta(email, agora)
            if len(falhas) == self.config.login_max_falhas_conta:
                self.evento(
                    "CONTA_BLOQUEADA",
                    email=email,
                    ip=ip,
                    target=user,
                    detalhe={
                        "falhas": len(falhas),
                        "minutos": self.config.login_bloqueio_minutos,
                    },
                )
                logger.warning("Conta %s bloqueada por tentativas (IP %s).", email, ip)
            if ip and len(self._falhas_do_ip(ip, agora)) == self.config.login_max_falhas_ip:
                self.evento("IP_BLOQUEADO", ip=ip, email=email, detalhe={})
                logger.warning("IP %s bloqueado por tentativas.", ip)

    def desbloquear(self, email: str, *, actor: User, ip: str | None = None) -> None:
        email = normalizar_email(email)
        self.registrar_tentativa(email=email, ip=None, motivo=DESBLOQUEIO)
        alvo = self.session.scalars(select(User).where(User.email == email)).first()
        self.evento("CONTA_DESBLOQUEADA", actor=actor, target=alvo, email=email, ip=ip)

    def evento(
        self,
        tipo: str,
        *,
        actor: User | None = None,
        target: User | None = None,
        email: str | None = None,
        ip: str | None = None,
        detalhe: dict | None = None,
    ) -> None:
        self.session.add(
            SecurityEvent(
                tipo=tipo,
                actor_id=actor.id if actor else None,
                target_id=target.id if target else None,
                email=email or (target.email if target else None),
                ip=ip,
                detalhe=detalhe or {},
            )
        )
        self.session.flush()

    def eventos(self, limite: int = 100) -> list[SecurityEvent]:
        return list(
            self.session.scalars(
                select(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limite)
            )
        )
