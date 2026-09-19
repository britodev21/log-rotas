"""Configuracao de log da aplicacao.

Deliberadamente simples: formato legivel no terminal durante o
desenvolvimento local. Log estruturado em JSON entra quando houver VPS e
agregador para consumir (ver docs/ARQUITETURA.md).
"""

import logging
import sys

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%H:%M:%S"))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # O SQLAlchemy em INFO despeja todo SQL executado; so queremos isso em debug.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO if debug else logging.WARNING)
