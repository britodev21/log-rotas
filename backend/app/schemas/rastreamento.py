"""Rastreamento ao vivo, previsão de chegada e navegação."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Motorista -> servidor
# --------------------------------------------------------------------------- #
class PosicaoIn(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    #: Hora do APARELHO, quando o GPS mediu — não a do envio. O celular
    #: pode passar minutos sem sinal e mandar tudo de uma vez depois.
    registrada_em: datetime
    precisao_m: float | None = None
    velocidade_mps: float | None = None
    direcao_graus: float | None = None


class EnvioPosicoes(BaseModel):
    #: Lote, porque o celular guarda o que não conseguiu mandar sem sinal.
    posicoes: list[PosicaoIn] = Field(min_length=1, max_length=500)


class ResultadoEnvioRead(BaseModel):
    aceitas: int
    #: Posição já recebida, reenviada como sinal de vida: renova o contato.
    repetidas: int = 0
    descartadas: int
    #: Por que cada grupo foi descartado. Descartar em silêncio esconderia um
    #: celular com GPS ruim ou relógio errado.
    motivos: dict[str, int]


# --------------------------------------------------------------------------- #
# Navegação
# --------------------------------------------------------------------------- #
class ManobraRead(BaseModel):
    tipo: str
    modificador: str | None
    instrucao: str
    rua: str
    distancia_m: int
    duracao_s: int
    latitude: float
    longitude: float
    saida: int | None


class ParadaNavegacaoRead(BaseModel):
    id: int
    tipo: str
    sequencia: int
    rotulo: str | None
    endereco: str | None
    latitude: float
    longitude: float
    status: str
    entregas: int


class NavegacaoRead(BaseModel):
    concluida: bool
    parada: ParadaNavegacaoRead | None = None
    #: Onde parar. Não é o pino da entrega: é o ponto na rua do endereço
    #: mais próximo dele, para a rota não chegar pela rua de trás.
    latitude_chegada: float | None = None
    longitude_chegada: float | None = None
    geometria: str | None = None
    manobras: list[ManobraRead] = Field(default_factory=list)
    distancia_m: int = 0
    duracao_s: int = 0
    chegada_prevista: datetime | None = None
    com_transito: bool = False
    #: Verdadeiro quando o serviço de rotas caiu e o trajeto é linha reta.
    estimada: bool = False
    aviso: str | None = None


# --------------------------------------------------------------------------- #
# Previsão e painel ao vivo
# --------------------------------------------------------------------------- #
class PrevisaoParadaRead(BaseModel):
    stop_id: int
    sequencia: int
    tipo: str
    rotulo: str | None
    status: str
    chegada_prevista: datetime | None
    chegada_planejada: datetime | None
    #: Positivo: atrasado em relação ao plano. Negativo: adiantado.
    atraso_s: int | None
    espera_s: int
    chegou_em: datetime | None


class PrevisaoRead(BaseModel):
    paradas: list[PrevisaoParadaRead]
    termino_previsto: datetime | None
    #: OSRM (rua livre), OSRM+TRANSITO, HAVERSINE (linha reta) ou PLANEJADO
    #: (sem posição ainda: são os horários do plano, não uma previsão).
    fonte: str
    com_transito: bool
    estimada: bool
    calculada_em: datetime
    posicao_de: datetime | None
    aviso: str | None


class PosicaoRead(BaseModel):
    latitude: float
    longitude: float
    precisao_m: float | None
    velocidade_mps: float | None
    direcao_graus: float | None
    registrada_em: datetime
    recebida_em: datetime


class RotaAoVivoRead(BaseModel):
    rota_id: int
    motorista: str | None
    veiculo: str | None
    placa: str | None
    #: EM_MOVIMENTO, PARADO, NA_PARADA, SEM_SINAL ou SEM_POSICAO.
    situacao: str
    posicao: PosicaoRead | None
    #: Segundos desde que o GPS mediu a última posição.
    idade_s: int | None
    #: Trajeto recente, [latitude, longitude], do mais antigo ao mais novo.
    rastro: list[list[float]]
    proxima: PrevisaoParadaRead | None
    feitas: int
    total: int
    previsao: PrevisaoRead


class AoVivoRead(BaseModel):
    rotas: list[RotaAoVivoRead]
    transito_configurado: bool
    gerado_em: datetime
