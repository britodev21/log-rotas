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


class DeliveryStatus(StrEnum):
    """Situacao de uma entrega.

    PENDENTE     cadastrada, ainda nao entrou em planejamento
    PLANEJADA    faz parte de um plano confirmado, aguardando a rota comecar
    EM_ROTA      o motorista iniciou a rota que a contem
    CHEGOU       o motorista chegou na parada
    ENTREGUE     concluida
    NAO_ENTREGUE tentativa sem sucesso, com motivo registrado
    CANCELADA    cancelada antes de ser executada
    """

    PENDENTE = "PENDENTE"
    PLANEJADA = "PLANEJADA"
    EM_ROTA = "EM_ROTA"
    CHEGOU = "CHEGOU"
    ENTREGUE = "ENTREGUE"
    NAO_ENTREGUE = "NAO_ENTREGUE"
    CANCELADA = "CANCELADA"


class Priority(StrEnum):
    BAIXA = "BAIXA"
    NORMAL = "NORMAL"
    ALTA = "ALTA"
    URGENTE = "URGENTE"


class FailureReason(StrEnum):
    """Por que a entrega nao aconteceu.

    Lista fechada de proposito: campo livre produziria vinte grafias do
    mesmo motivo e nenhum relatorio confiavel. `OUTRO` existe para o que
    escapa, sempre acompanhado de observacao.
    """

    CLIENTE_AUSENTE = "CLIENTE_AUSENTE"
    ENDERECO_INCORRETO = "ENDERECO_INCORRETO"
    RECUSA = "RECUSA"
    ESTABELECIMENTO_FECHADO = "ESTABELECIMENTO_FECHADO"
    PROBLEMA_ACESSO = "PROBLEMA_ACESSO"
    AVARIA = "AVARIA"
    FALTA_PRODUTO = "FALTA_PRODUTO"
    OUTRO = "OUTRO"


class RouteStatus(StrEnum):
    RASCUNHO = "RASCUNHO"
    PLANEJADA = "PLANEJADA"
    INICIADA = "INICIADA"
    FINALIZADA = "FINALIZADA"
    CANCELADA = "CANCELADA"


class PlanStatus(StrEnum):
    RASCUNHO = "RASCUNHO"
    CONFIRMADO = "CONFIRMADO"
    DESCARTADO = "DESCARTADO"


class StopType(StrEnum):
    """Tipo de parada numa rota.

    BASE_RECARGA existe desde ja, embora o MVP so gere rotas
    BASE_SAIDA -> ENTREGA* -> BASE_RETORNO. Custa um valor de enum hoje e e
    o que torna o retorno a base para recarregar implementavel depois sem
    migracao destrutiva na tabela que mais tera linhas.
    """

    BASE_SAIDA = "BASE_SAIDA"
    ENTREGA = "ENTREGA"
    BASE_RECARGA = "BASE_RECARGA"
    BASE_RETORNO = "BASE_RETORNO"


class StopStatus(StrEnum):
    PENDENTE = "PENDENTE"
    CHEGOU = "CHEGOU"
    CONCLUIDA = "CONCLUIDA"
    PULADA = "PULADA"


class MatrixSource(StrEnum):
    """De onde vieram distancia e duracao.

    HAVERSINE e linha reta com fator de correcao, NAO distancia de estrada.
    Sempre que uma rota for calculada com ela, a interface precisa dizer
    isso — e a diferenca entre estimar e mentir.
    """

    OSRM = "OSRM"
    HAVERSINE = "HAVERSINE"
