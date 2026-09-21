"""Schemas de geocodificacao."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.core.enums import GeocodePrecision, GeocodeStatus

TipoAlvo = Literal["entrega", "cliente", "base"]


class CoordenadaManual(BaseModel):
    """Pino ajustado a mao pelo administrador."""

    latitude: Annotated[float, Field(ge=-90, le=90)]
    longitude: Annotated[float, Field(ge=-180, le=180)]


class CandidatoRead(BaseModel):
    latitude: float
    longitude: float
    display_name: str
    precision: GeocodePrecision | None


class GeocodeTentativaRead(BaseModel):
    status: str
    latitude: float | None = None
    longitude: float | None = None
    precision: GeocodePrecision | None = None
    normalized_address: str | None = None
    provider: str
    error: str | None = None
    candidatos: list[CandidatoRead] = []


class LoteRequest(BaseModel):
    tipo: TipoAlvo = "entrega"
    limite: Annotated[int, Field(ge=1, le=200)] = 50
    forcar: bool = False


class LoteResultado(BaseModel):
    processados: int
    ok: int
    ambiguo: int
    falhou: int
    manual: int
    erro_provedor: int


class PendenteRead(BaseModel):
    tipo: TipoAlvo
    id: int
    titulo: str
    address: str | None
    geocode_status: GeocodeStatus
    geocode_precision: GeocodePrecision | None = None
    #: Por que este registro esta na fila, em uma linha, escrito para quem
    #: vai resolver. "sem coordenada" e "posicao aproximada: ..." exigem
    #: acoes diferentes, e um rotulo generico esconderia isso.
    motivo: str | None = None
    geocode_error: str | None
    latitude: float | None
    longitude: float | None


class EnderecoCepRead(BaseModel):
    """Endereco resolvido a partir do CEP."""

    cep: str
    cep_formatado: str
    logradouro: str | None
    bairro: str | None
    cidade: str
    uf: str
    #: Endereco de uma linha ja montado na ordem que o geocodificador espera.
    #: O numero entra pela query, porque o CEP sozinho nao o conhece.
    endereco_montado: str

    #: Centro do TRECHO de rua do CEP, para o mapa abrir na quadra certa.
    #: Nao e o ponto da entrega: aponta a quadra, nao a porta, e nao passa
    #: na regra de app/services/precisao.py. Nulo quando a fonte nao sabe.
    latitude: float | None = None
    longitude: float | None = None


class BuscaResultado(BaseModel):
    """Candidatos de uma busca livre, para a pessoa escolher no mapa."""

    consulta: str
    candidatos: list[CandidatoRead]


class RecursosRead(BaseModel):
    """O que esta ligado, para a tela escolher o fluxo sem tentativa e erro."""

    #: Busca com sugestoes do Google. Desligada, a tela usa o fluxo por CEP.
    autocomplete: bool


class SugestaoRead(BaseModel):
    place_id: str
    texto: str
    principal: str
    secundario: str


class LugarRead(BaseModel):
    """Lugar escolhido na busca do Google, pronto para o formulario."""

    place_id: str
    endereco_formatado: str
    latitude: float
    longitude: float
    #: EXATO so quando a Geocoding API confirmou ROOFTOP. Qualquer outra
    #: coisa pede conferencia no mapa.
    precision: GeocodePrecision
    #: ROOFTOP, RANGE_INTERPOLATED... Nulo quando nao foi possivel saber —
    #: e a tela precisa dizer isso, nao esconder.
    tipo_ponto: str | None
    logradouro: str | None
    numero: str | None
    bairro: str | None
    cidade: str | None
    uf: str | None
    cep: str | None
