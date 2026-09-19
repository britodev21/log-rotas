"""Enumeracoes de dominio do Log Rotas.

Convencao: os valores sao ASCII e em MAIUSCULAS (NAO_ENTREGUE, nao
"NAO_ENTREGUE" com acento). Acento em identificador quebra URL, CSV e
integracao. A traducao para exibicao ("Nao entregue") acontece no frontend.

Os valores sao persistidos como VARCHAR + CHECK constraint, e nao como tipo
ENUM nativo do Postgres, porque adicionar um valor novo a um ENUM nativo torna
a migration dolorosa — e esta lista vai crescer (ver docs/ARQUITETURA.md).
"""

from enum import StrEnum


class Role(StrEnum):
    ADMIN = "ADMIN"
    MOTORISTA = "MOTORISTA"


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
