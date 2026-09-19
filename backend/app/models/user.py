"""Usuario do sistema — quem faz login no Log Rotas.

Nao confundir com Driver (Fase 3): Driver e o perfil operacional do motorista
e pode existir sem usuario (motorista terceirizado, sem acesso ao sistema).
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Identity, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import Role
from app.db.base import Base, TimestampMixin

_ROLES = ", ".join(f"'{r.value}'" for r in Role)


class User(Base, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"role IN ({_ROLES})", name="role_valido"),
        CheckConstraint("email = lower(email)", name="email_minusculo"),
        {"comment": "Usuarios que autenticam no sistema."},
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)

    # Unico globalmente. A aplicacao normaliza para minusculas antes de gravar,
    # e a CHECK acima impede que qualquer outro caminho grave em maiusculas —
    # sem isso, "Joao@x.com" e "joao@x.com" seriam contas diferentes.
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[str] = mapped_column(String(20), nullable=False)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    # Coluna presente desde a primeira migration, verificacao desligada no MVP:
    # exigir confirmacao por e-mail sem SMTP configurado travaria o primeiro
    # acesso. Pendencia registrada em docs/LIMITACOES.md.
    email_verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )

    # Incrementar este numero invalida imediatamente todos os tokens ja
    # emitidos para o usuario (troca de senha, desligamento).
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de debug
        return f"<User id={self.id} email={self.email!r} role={self.role}>"
