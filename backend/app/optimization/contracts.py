"""Contratos do motor de otimizacao.

Dataclasses puras. Este modulo NAO importa SQLAlchemy, NAO importa FastAPI e
nao sabe o que e uma entrega no banco.

Isso nao e purismo. E o que permite: rodar o solver num teste sem subir
banco, trocar o motor sem tocar no resto, e reproduzir um caso problematico
de producao a partir de um JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class SolverStatus(StrEnum):
    OTIMO = "OTIMO"
    VIAVEL = "VIAVEL"
    INVIAVEL = "INVIAVEL"
    TEMPO_ESGOTADO = "TEMPO_ESGOTADO"
    ERRO = "ERRO"


@dataclass(frozen=True)
class Demanda:
    """Quanto uma parada consome de cada dimensao.

    Todas opcionais porque ainda nao se sabe o que limita a operacao da
    Britto. O solver so cria a restricao para a dimensao que estiver
    preenchida NOS DOIS LADOS — parada e veiculo. Dimensao pela metade seria
    restricao inventada.
    """

    peso_kg: float | None = None
    volume_m3: float | None = None
    comprimento_m: float | None = None
    #: Quantas pessoas a parada exige. Diferente das outras: nao se acumula
    #: ao longo da rota, e um maximo — o veiculo precisa levar pelo menos
    #: tantas pessoas quanto a parada mais exigente.
    equipe: int = 1


@dataclass(frozen=True)
class JanelaHorario:
    """Intervalo em segundos desde o inicio do turno."""

    inicio_s: int
    fim_s: int


@dataclass(frozen=True)
class ParadaPlanejada:
    """Um lugar a visitar, com tudo que o solver precisa saber."""

    id: str
    latitude: float
    longitude: float
    rotulo: str
    #: Quanto tempo a equipe fica parada ali. Numa operacao dentro de Campo
    #: Grande, com deslocamentos de 10 a 25 minutos, E ESTE numero que
    #: determina quantos servicos cabem no dia — nao a quilometragem.
    tempo_servico_s: int
    demanda: Demanda = field(default_factory=Demanda)
    janela: JanelaHorario | None = None
    #: 0 = mais urgente. Usado como penalidade para dispensar uma parada:
    #: quanto menor o numero, mais caro deixar de atende-la.
    prioridade: int = 2
    #: Ids das entregas do dominio resolvidas nesta parada.
    entregas: tuple[str, ...] = ()


@dataclass(frozen=True)
class VeiculoDisponivel:
    """Um veiculo e seus limites."""

    id: str
    rotulo: str
    capacidade_peso_kg: float | None = None
    capacidade_volume_m3: float | None = None
    capacidade_comprimento_m: float | None = None
    max_paradas: int | None = None
    tamanho_equipe: int = 1
    #: Duracao maxima do turno, em segundos. Limite real da jornada.
    jornada_s: int = 8 * 3600


@dataclass(frozen=True)
class OpcoesOtimizacao:
    #: Quanto tempo o solver pode procurar. Nao e o tempo da requisicao:
    #: o runner impoe um limite maior e mata o processo se estourar.
    limite_tempo_s: int = 10
    #: Permite deixar paradas de fora quando nao cabem. Com False, uma unica
    #: parada impossivel torna o problema inteiro inviavel — e a resposta
    #: vira "nao consegui", sem dizer qual parada e o problema.
    permitir_dispensar: bool = True
    #: Segundos desde a meia-noite em que o turno comeca.
    inicio_turno_s: int = 8 * 3600
    #: Quantas vezes cada veiculo pode sair da base no dia. Com mais de uma,
    #: ele volta, recarrega e sai de novo — tudo dentro da mesma jornada.
    max_viagens: int = 1
    #: Tempo parado na base entre uma viagem e a proxima (carregar o
    #: caminhao de novo).
    recarga_s: int = 30 * 60


@dataclass(frozen=True)
class OptimizationRequest:
    """Tudo que o solver precisa. Nada alem disso."""

    deposito: ParadaPlanejada
    paradas: list[ParadaPlanejada]
    veiculos: list[VeiculoDisponivel]
    #: duracoes[i][j] em segundos; indice 0 e o deposito.
    duracoes: list[list[int]]
    #: distancias[i][j] em metros; indice 0 e o deposito.
    distancias: list[list[int]]
    opcoes: OpcoesOtimizacao = field(default_factory=OpcoesOtimizacao)

    def validar(self) -> list[str]:
        """Problemas que tornam o calculo impossivel ou sem sentido.

        Detectados ANTES de chamar o solver, para a resposta poder dizer o
        que esta errado em vez de apenas "sem solucao" — que nao ajuda
        ninguem a consertar nada.
        """
        erros: list[str] = []
        n = len(self.paradas) + 1

        if not self.paradas:
            erros.append("Nenhuma parada para roteirizar.")
        if not self.veiculos:
            erros.append("Nenhum veiculo disponivel.")
        if len(self.duracoes) != n or any(len(linha) != n for linha in self.duracoes):
            erros.append("A matriz de duracoes nao corresponde ao numero de pontos.")
        if len(self.distancias) != n or any(len(linha) != n for linha in self.distancias):
            erros.append("A matriz de distancias nao corresponde ao numero de pontos.")

        # Parada que exige mais gente do que qualquer veiculo leva nunca
        # sera atendida. Melhor dizer isso agora, com o nome da parada.
        maior_equipe = max((v.tamanho_equipe for v in self.veiculos), default=0)
        impossiveis = [p.rotulo for p in self.paradas if p.demanda.equipe > maior_equipe]
        if impossiveis:
            erros.append(
                "Nenhum veiculo tem equipe suficiente para: " + ", ".join(impossiveis[:5])
            )

        return erros


@dataclass
class ParadaResolvida:
    parada_id: str
    ordem: int
    chegada_estimada_s: int
    distancia_do_anterior_m: int
    duracao_do_anterior_s: int
    #: Em qual saida da base o veiculo leva esta parada (1, 2, ...).
    viagem: int = 1


@dataclass
class RecargaResolvida:
    """A volta a base entre duas viagens."""

    #: A viagem que comeca depois desta recarga (2, 3, ...).
    viagem: int
    #: Chega na base: fim da viagem anterior.
    chegada_s: int
    #: Sai de novo, carregado: inicio desta viagem.
    saida_s: int
    distancia_do_anterior_m: int
    duracao_do_anterior_s: int


@dataclass
class RotaResolvida:
    veiculo_id: str
    paradas: list[ParadaResolvida]
    distancia_total_m: int
    duracao_total_s: int
    carga_peso_kg: float
    carga_volume_m3: float
    recargas: list[RecargaResolvida] = field(default_factory=list)
    #: Sai da base (inicio da primeira viagem) e volta de vez (fim da ultima).
    saida_s: int = 0
    chegada_base_s: int | None = None
    retorno_distancia_m: int = 0
    retorno_duracao_s: int = 0

    @property
    def quantidade_paradas(self) -> int:
        return len(self.paradas)

    @property
    def quantidade_viagens(self) -> int:
        return len(self.recargas) + 1


@dataclass
class ParadaDispensada:
    parada_id: str
    rotulo: str
    motivo: str


@dataclass
class OptimizationResult:
    """O que o solver conseguiu, e o que nao conseguiu.

    `dispensadas` nunca e omitido. Uma parada que sai do plano em silencio e
    uma entrega que ninguem vai fazer e ninguem vai perceber.
    """

    status: SolverStatus
    rotas: list[RotaResolvida] = field(default_factory=list)
    dispensadas: list[ParadaDispensada] = field(default_factory=list)
    mensagem: str = ""
    solver: str = ""
    tempo_ms: int = 0
    estatisticas: dict = field(default_factory=dict)

    @property
    def sucesso(self) -> bool:
        return self.status in (SolverStatus.OTIMO, SolverStatus.VIAVEL)

    @property
    def distancia_total_m(self) -> int:
        return sum(r.distancia_total_m for r in self.rotas)

    @property
    def duracao_total_s(self) -> int:
        return sum(r.duracao_total_s for r in self.rotas)
