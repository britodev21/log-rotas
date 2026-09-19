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


class GeocodeStatus(StrEnum):
    """Situacao da conversao de endereco em coordenada.

    A distincao entre os estados e o que torna possivel a fila de revisao de
    enderecos da Fase 4: sem ela nao da para separar "ainda nao tentei" de
    "tentei e falhou" de "o administrador corrigiu o pino na mao".

    MANUAL nunca e sobrescrito por geocodificacao automatica.
    """

    PENDENTE = "PENDENTE"
    OK = "OK"
    AMBIGUO = "AMBIGUO"
    FALHOU = "FALHOU"
    MANUAL = "MANUAL"


class GeocodePrecision(StrEnum):
    """Quao fundo o provedor conseguiu resolver o endereco.

    Importa para o planejamento: uma coordenada no nivel de BAIRRO pode
    colocar a parada a centenas de metros do portao, e a rota calculada em
    cima dela e otimista. A Fase 7 usara isso para avisar antes de confirmar.
    """

    EXATO = "EXATO"
    RUA = "RUA"
    BAIRRO = "BAIRRO"
    CIDADE = "CIDADE"
