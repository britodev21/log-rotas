"""Tarefas de manutenção pela linha de comando.

    python -m app.tarefas limpar

Faz o mesmo que o agendador faz sozinho às 3h, e o mesmo que o botão
"Limpar agora" da tela de Segurança. Útil para um cron do servidor, se um
dia o agendador interno for desligado (LIMPEZA_HORA=-1).
"""

from __future__ import annotations

import sys

from app.db.session import SessionLocal
from app.services.manutencao import MANUAL, limpar


def main(argumentos: list[str]) -> int:
    if argumentos != ["limpar"]:
        print("uso: python -m app.tarefas limpar")
        return 2
    with SessionLocal() as session:
        execucao = limpar(session, origem=MANUAL)
    if execucao is None:
        print("Outra limpeza esta em andamento; nada foi feito.")
        return 1
    print(f"Limpeza concluida: {execucao.resultado}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
