"""Matriz de tempo com o trânsito previsto, para o planejamento.

O PROBLEMA. O otimizador decide com a matriz de tempo entre todos os pares
de pontos. Com o OSRM essa matriz é de rua vazia — e, medido em Campo
Grande, otimista: num mesmo trajeto o OSRM previu 4 min e o Google, com
trânsito, 7 min 53 s. Com a matriz otimista o plano promete horários que o
caminhão não cumpre e põe no dia mais entregas do que cabem.

POR QUE NÃO A MATRIZ DO GOOGLE. A Routes API tem um método de matriz
(computeRouteMatrix), mas ele exige faturamento ativo no projeto — conferido
em 22/09/2026: 403. E é cobrado por PAR de pontos: 20 paradas são 441 pares
a cada cálculo.

O QUE ESTE MÓDULO FAZ. Usa a chamada de rota comum (computeRoutes), que
funciona sem faturamento e devolve o tempo de cada perna de uma rota com até
25 pontos intermediários. Uma rota A→B→C→D mede três pares de uma vez. Então
o problema vira: passar por todos os pares da matriz com o menor número de
rotas. É o circuito de Euler: num grafo em que cada ponto tem tantas saídas
quanto entradas, existe um caminho que usa cada arco exatamente uma vez. A
matriz completa é esse grafo — então um só caminho passa por todos os pares,
e ele é cortado em pedaços de 26 pernas. Com 20 paradas: 441 pares viram
~17 chamadas.

HORA. O Google recebe a hora de partida do turno, no dia do plano, e devolve
o trânsito PREVISTO para aquela hora. Dentro de cada chamada, as pernas
seguintes são calculadas com a hora avançando — sem as paradas, porque o
Google não sabe delas. Medido em Campo Grande para uma quarta-feira: o
tempo varia pouco ao longo do dia útil (7h a 15h: ±3%; 18h: +7%) e muito
contra a madrugada (3h: -35%). O que o trânsito corrige, na prática, é a
diferença entre rua cheia e rua vazia — e o otimismo do OSRM.

CUSTO. Cada chamada é uma consulta ao Google. O plano registra quantas foram
feitas. Recalcular o mesmo dia reaproveita os pares já consultados
(tabela trafego_trechos). Acima de `traffic_max_consultas_plano`, os pares que
faltam usam o tempo do OSRM multiplicado pelo fator medido nos que foram
consultados — e o plano diz quantos pares vieram de cada jeito.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import MatrixSource
from app.models.trafego import TrafficLeg
from app.routing import transito
from app.routing.base import Matriz

logger = logging.getLogger(__name__)

#: Pernas por chamada: origem + 25 intermediários + destino.
PERNAS_POR_CONSULTA = transito.MAXIMO_INTERMEDIARIOS + 1
CONSULTAS_SIMULTANEAS = 4

_VIRTUAL = -1


def chave(latitude: float, longitude: float) -> str:
    """Pinos a menos de ~1 m um do outro são o mesmo lugar."""
    return f"{latitude:.5f},{longitude:.5f}"


# --------------------------------------------------------------------------- #
# Cobertura dos pares por caminhos
# --------------------------------------------------------------------------- #
def _circuito(saidas: dict[int, list[int]], inicio: int) -> list[int]:
    """Hierholzer: percorre cada arco uma vez, a partir de `inicio`."""
    pilha, circuito = [inicio], []
    while pilha:
        no = pilha[-1]
        if saidas[no]:
            pilha.append(saidas[no].pop())
        else:
            circuito.append(pilha.pop())
    circuito.reverse()
    return circuito


def trilhas(arcos: Iterable[tuple[int, int]]) -> list[list[int]]:
    """O menor número de caminhos que passam por cada arco exatamente uma vez.

    Onde um ponto tem mais saídas que entradas (ou o contrário), um caminho
    precisa começar (ou terminar) ali. Um ponto VIRTUAL liga esses
    desequilíbrios, o grafo fica equilibrado, o circuito de Euler existe, e
    cortá-lo no ponto virtual dá os caminhos.
    """
    saidas: dict[int, list[int]] = defaultdict(list)
    saldo: dict[int, int] = defaultdict(int)
    for a, b in arcos:
        saidas[a].append(b)
        saldo[a] += 1
        saldo[b] -= 1
    for no, s in list(saldo.items()):
        if s > 0:
            saidas[_VIRTUAL].extend([no] * s)
        elif s < 0:
            saidas[no].extend([_VIRTUAL] * -s)

    resultado: list[list[int]] = []
    for inicio in [_VIRTUAL, *list(saidas)]:
        if not saidas[inicio]:
            continue
        atual: list[int] = []
        for no in _circuito(saidas, inicio):
            if no == _VIRTUAL:
                if len(atual) > 1:
                    resultado.append(atual)
                atual = []
            else:
                atual.append(no)
        if len(atual) > 1:
            resultado.append(atual)
    return resultado


def sequencias(
    arcos: Iterable[tuple[int, int]], pernas: int = PERNAS_POR_CONSULTA
) -> list[list[int]]:
    """Sequências de pontos, cada uma com no máximo `pernas` pernas.

    Os caminhos são emendados antes de cortar: o fim de um liga no começo
    do próximo com uma perna a mais. A perna de emenda é medida à toa, mas
    economiza uma chamada inteira — e é a chamada que custa.
    """
    sequencia: list[int] = []
    for trilha in trilhas(arcos):
        if sequencia and sequencia[-1] == trilha[0]:
            sequencia.extend(trilha[1:])
        else:
            sequencia.extend(trilha)
    return [sequencia[i : i + pernas + 1] for i in range(0, max(len(sequencia) - 1, 0), pernas)]


# --------------------------------------------------------------------------- #
# Matriz
# --------------------------------------------------------------------------- #
@dataclass
class ResumoTransito:
    """O que foi feito para montar a matriz — gravado no plano."""

    partida: datetime
    consultas: int = 0
    consultas_com_falha: int = 0
    pares_google: int = 0
    pares_do_cache: int = 0
    pares_por_fator: int = 0
    #: Tempo com trânsito ÷ tempo do OSRM, nos pares consultados.
    fator: float = 1.0
    falhas: list[str] = field(default_factory=list)

    def como_dict(self) -> dict:
        return {
            "partida": self.partida.isoformat(),
            "consultas": self.consultas,
            "consultas_com_falha": self.consultas_com_falha,
            "pares_google": self.pares_google,
            "pares_do_cache": self.pares_do_cache,
            "pares_por_fator": self.pares_por_fator,
            "fator": round(self.fator, 3),
        }


def partida_efetiva(partida: datetime) -> datetime:
    """A hora usada: a do turno, ou agora se o turno já começou."""
    agora = datetime.now(UTC)
    return partida if partida > agora else agora


def _hora_cheia(momento: datetime) -> datetime:
    return momento.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


class MatrizComTransito:
    """Troca os tempos de uma matriz pelos do Google com trânsito."""

    def __init__(self, session: Session, consultar=None) -> None:
        self.session = session
        # Injetável nos testes: a suíte não fala com o Google.
        self.consultar = consultar or transito.consultar

    def aplicar(self, livre: Matriz, partida: datetime) -> tuple[Matriz, ResumoTransito]:
        """`livre` é a matriz da rua vazia (OSRM); ela dá o fator e o reserva.

        Levanta `transito.TransitoIndisponivel` se nenhum par puder ser
        medido — quem chama segue com a matriz livre e diz isso no plano.
        """
        settings = get_settings()
        inicio = time.monotonic()
        efetiva = partida_efetiva(partida)
        hora = _hora_cheia(efetiva)
        resumo = ResumoTransito(partida=efetiva)

        chaves = [chave(p.latitude, p.longitude) for p in livre.pontos]
        lugares = list(dict.fromkeys(chaves))
        coordenadas = {
            c: (p.latitude, p.longitude) for c, p in zip(chaves, livre.pontos, strict=True)
        }
        # Um índice qualquer de cada lugar, para ler a matriz livre.
        indice = {c: chaves.index(c) for c in lugares}

        medidos = self._do_cache(lugares, hora)
        resumo.pares_do_cache = len(medidos)

        faltando = [
            (a, b)
            for a in range(len(lugares))
            for b in range(len(lugares))
            if a != b and (lugares[a], lugares[b]) not in medidos
        ]
        pedidos = sequencias(faltando)
        limite = settings.traffic_max_consultas_plano
        if len(pedidos) > limite:
            logger.info("Transito: %s consultas necessarias, limite %s.", len(pedidos), limite)
            pedidos = pedidos[:limite]

        novos = self._consultar_todos(pedidos, lugares, coordenadas, efetiva, resumo)
        medidos.update(novos)
        self._guardar(novos, hora)

        if not medidos:
            causa = resumo.falhas[0] if resumo.falhas else "nenhum par consultado"
            raise transito.TransitoIndisponivel(causa)

        # Fator nos pares medidos: cobre os que não foram.
        soma_google = soma_livre = 0
        for (a, b), (duracao, _) in medidos.items():
            base = livre.duracoes[indice[a]][indice[b]]
            if base > 0 and duracao > 0:
                soma_google += duracao
                soma_livre += base
        if soma_livre:
            resumo.fator = max(
                transito.FATOR_MINIMO, min(transito.FATOR_MAXIMO, soma_google / soma_livre)
            )

        n = len(livre.pontos)
        duracoes = [[0] * n for _ in range(n)]
        distancias = [[0] * n for _ in range(n)]
        por_fator: set[tuple[str, str]] = set()
        for i in range(n):
            for j in range(n):
                a, b = chaves[i], chaves[j]
                if a == b:
                    continue
                if (a, b) in medidos:
                    duracoes[i][j], distancias[i][j] = medidos[(a, b)]
                else:
                    duracoes[i][j] = round(livre.duracoes[i][j] * resumo.fator)
                    distancias[i][j] = livre.distancias[i][j]
                    por_fator.add((a, b))

        resumo.pares_por_fator = len(por_fator)
        resumo.pares_google = len(medidos)
        logger.info(
            "Transito: %s consultas (%s falhas) em %s ms; %s pares medidos, %s do cache, "
            "%s por fator; fator %.2f.",
            resumo.consultas, resumo.consultas_com_falha,
            round((time.monotonic() - inicio) * 1000), len(medidos), resumo.pares_do_cache,
            len(por_fator), resumo.fator,
        )

        avisos = list(livre.avisos)
        if resumo.consultas_com_falha:
            avisos.append(
                f"{resumo.consultas_com_falha} de {resumo.consultas} consultas de transito "
                f"falharam ({resumo.falhas[0]}). Os trechos que faltaram usam o tempo da "
                f"rua livre x {resumo.fator:.2f}, o fator medido nos demais."
            )
        elif por_fator:
            avisos.append(
                f"{len(por_fator)} de {len(por_fator) + len(medidos)} trechos passaram do "
                f"limite de consultas ao Google e usam o tempo da rua livre x "
                f"{resumo.fator:.2f}, o fator medido nos demais."
            )

        matriz = Matriz(
            pontos=livre.pontos,
            distancias=distancias,
            duracoes=duracoes,
            source=MatrixSource.GOOGLE_TRANSITO,
            # Pares cobertos pelo fator herdam a natureza da matriz livre.
            estimada=livre.estimada and bool(por_fator),
            detalhe=(
                f"Google Routes, transito previsto para {efetiva.isoformat()}; "
                f"{len(medidos)} pares medidos, {len(por_fator)} por fator."
            ),
            avisos=avisos,
        )
        return matriz, resumo

    # ------------------------------------------------------------------ #
    def _consultar_todos(self, pedidos, lugares, coordenadas, partida, resumo):
        def um(sequencia: list[int]):
            pontos = [coordenadas[lugares[k]] for k in sequencia]
            return sequencia, self.consultar(pontos, partida)

        novos: dict[tuple[str, str], tuple[int, int]] = {}
        if not pedidos:
            return novos
        with ThreadPoolExecutor(max_workers=CONSULTAS_SIMULTANEAS) as execucao:
            futuros = [execucao.submit(um, p) for p in pedidos]
            for futuro in futuros:
                resumo.consultas += 1
                try:
                    sequencia, tempo = futuro.result()
                except transito.TransitoIndisponivel as exc:
                    resumo.consultas_com_falha += 1
                    resumo.falhas.append(str(exc))
                    continue
                pernas = len(sequencia) - 1
                if len(tempo.duracoes_s) != pernas or len(tempo.distancias_m) != pernas:
                    resumo.consultas_com_falha += 1
                    resumo.falhas.append("o Google devolveu um numero de trechos diferente")
                    continue
                for k in range(pernas):
                    par = (lugares[sequencia[k]], lugares[sequencia[k + 1]])
                    novos[par] = (tempo.duracoes_s[k], tempo.distancias_m[k])
        return novos

    def _do_cache(self, lugares: list[str], hora: datetime) -> dict:
        linhas = self.session.execute(
            select(TrafficLeg.origem, TrafficLeg.destino, TrafficLeg.duracao_s,
                   TrafficLeg.distancia_m)
            .where(
                TrafficLeg.partida == hora,
                TrafficLeg.origem.in_(lugares),
                TrafficLeg.destino.in_(lugares),
            )
        )
        return {(o, d): (dur, dist) for o, d, dur, dist in linhas}

    def _guardar(self, novos: dict, hora: datetime) -> None:
        if not novos:
            return
        linhas = [
            {"origem": a, "destino": b, "partida": hora, "duracao_s": dur, "distancia_m": dist}
            for (a, b), (dur, dist) in novos.items()
        ]
        comando = insert(TrafficLeg).values(linhas)
        comando = comando.on_conflict_do_update(
            index_elements=["origem", "destino", "partida"],
            set_={
                "duracao_s": comando.excluded.duracao_s,
                "distancia_m": comando.excluded.distancia_m,
                "consultado_em": datetime.now(UTC),
            },
        )
        self.session.execute(comando)
