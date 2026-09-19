"""Engine, fabrica de sessoes e a dependencia get_db.

SQLAlchemy sincrono por decisao de arquitetura: os endpoints sao `def` e o
FastAPI os executa em threadpool. Async ORM traria armadilhas de sessao sem
ganho real no volume desta operacao (ver docs/ARQUITETURA.md).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_settings = get_settings()

engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,  # descarta conexoes mortas apos ociosidade
    echo=False,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Sessao por requisicao, com rollback automatico em caso de excecao."""
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
