"""Primeiro acesso: cria a empresa e o administrador inicial.

Nao existe auto-cadastro publico no Log Rotas — ele e a aplicacao de uma
empresa so, e um cadastro aberto seria uma porta para estranhos criarem conta.
Esta rota funciona enquanto o sistema esta vazio e se fecha para sempre depois
que o primeiro usuario existe. Dai em diante quem cria usuarios e o ADMIN.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import Role
from app.core.errors import ConflictError
from app.core.security import hash_password
from app.core.senha import exigir_senha_valida
from app.models.company_settings import SETTINGS_ID, CompanySettings
from app.models.user import User
from app.repositories.company_settings_repository import CompanySettingsRepository
from app.repositories.user_repository import UserRepository
from app.schemas.setup import SetupRequest

logger = logging.getLogger(__name__)


class SetupService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.settings_repo = CompanySettingsRepository(session)

    def needs_setup(self) -> bool:
        return not self.users.exists_any()

    def run(self, payload: SetupRequest) -> User:
        if self.users.exists_any():
            # Fechada de forma permanente: se ja existe usuario, esta rota nao
            # pode mais criar nada, ou viraria um cadastro publico de ADMIN.
            raise ConflictError(
                "O sistema ja foi configurado. Peca a um administrador para criar seu acesso."
            )

        env = get_settings()
        exigir_senha_valida(
            payload.admin_password, email=payload.admin_email, nome=payload.admin_name
        )

        # Empresa e admin nascem na MESMA transacao: um sistema com usuario e
        # sem configuracao (ou o contrario) seria um estado invalido.
        self.settings_repo.add(
            CompanySettings(
                id=SETTINGS_ID,
                company_name=payload.company_name.strip(),
                timezone=env.default_timezone,
                default_stop_service_minutes=env.default_stop_service_minutes,
            )
        )

        admin = self.users.add(
            User(
                name=payload.admin_name.strip(),
                email=payload.admin_email,
                password_hash=hash_password(payload.admin_password),
                role=Role.ADMIN.value,
                active=True,
            )
        )

        self.session.commit()
        logger.info(
            "Primeiro acesso concluido: empresa %r, admin %s.",
            payload.company_name,
            admin.email,
        )
        return admin
