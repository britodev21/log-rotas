"""Agrupamento de entregas em paradas.

Uma parada e uma VISITA FISICA, nao uma entrega. O motorista estaciona uma
vez e resolve tudo que houver naquele lugar: predio, condominio, galeria,
duas compras do mesmo cliente.

Isso acontece ANTES da matriz de distancias, e nao e detalhe de
apresentacao — muda o problema que o solver resolve:

- 40 entregas podem virar 31 paradas, e a matriz cai de 41x41 para 32x32;
- o tempo de servico deixa de ser a soma ingenua: quem estaciona uma vez
  nao paga o tempo de estacionar tres vezes;
- entregas do mesmo lugar vao obrigatoriamente no mesmo veiculo, que e o
  comportamento correto e sairia de graca.

Funcao pura: recebe entregas, devolve paradas. Sem banco, sem HTTP.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from app.models.delivery import Delivery
from app.services.precisao import confiavel as precisao_confiavel

logger = logging.getLogger(__name__)

#: Casas decimais usadas para considerar duas coordenadas "o mesmo lugar".
#: Quatro casas ~ 11 metros: a largura de uma fachada. Cinco casas separaria
#: portas vizinhas do mesmo predio; tres juntaria a quadra inteira.
PRECISAO_AGRUPAMENTO = 4

#: Tempo gasto so para chegar, estacionar e sair — pago uma vez por parada,
#: independentemente de quantas entregas sejam resolvidas ali.
TEMPO_BASE_PARADA_S = 5 * 60


@dataclass
class ParadaAgrupada:
    """Um lugar a visitar e as entregas que serao resolvidas ali."""

    chave: str
    latitude: float
    longitude: float
    rotulo: str
    endereco: str | None
    entregas: list[Delivery] = field(default_factory=list)

    @property
    def ids(self) -> list[int]:
        return [e.id for e in self.entregas]

    @property
    def peso_kg(self) -> float:
        return float(sum(e.weight_kg or 0 for e in self.entregas))

    @property
    def volume_m3(self) -> float:
        return float(sum(e.volume_m3 or 0 for e in self.entregas))

    @property
    def comprimento_m(self) -> float:
        # Comprimento NAO soma: cabe a maior peca, nao a soma delas. Somar
        # diria que tres corrimoes de 2 m precisam de um veiculo de 6 m.
        return float(max((e.length_m or 0 for e in self.entregas), default=0))

    @property
    def equipe(self) -> int:
        # Tambem nao soma: vale a entrega mais exigente da parada.
        return max((e.required_crew or 1 for e in self.entregas), default=1)

    @property
    def prioridade(self) -> str:
        ordem = ["URGENTE", "ALTA", "NORMAL", "BAIXA"]
        presentes = [e.priority for e in self.entregas if e.priority in ordem]
        return min(presentes, key=ordem.index) if presentes else "NORMAL"

    def tempo_servico_s(self, tempo_padrao_min: int) -> int:
        """Tempo base da parada + tempo de cada entrega.

        Nao e a soma pura dos tempos: quem estaciona uma vez nao paga o
        tempo de estacionar N vezes. Somar superestimaria a rota e faria o
        planejamento caber menos servicos do que o dia comporta.
        """
        por_entrega = sum(
            (e.service_time_minutes or tempo_padrao_min) * 60 for e in self.entregas
        )
        return TEMPO_BASE_PARADA_S + por_entrega

    def janela(self) -> tuple[int, int] | None:
        """Interseccao das janelas das entregas, em segundos do dia.

        Se uma entrega so pode ser recebida de 8h as 10h e outra de 9h as
        12h, a parada inteira so pode acontecer entre 9h e 10h. Interseccao
        vazia significa que elas nao podem ser visitadas juntas — tratado
        por quem chama, separando o grupo.
        """
        janelas = [
            (
                e.time_window_start.hour * 3600 + e.time_window_start.minute * 60,
                e.time_window_end.hour * 3600 + e.time_window_end.minute * 60,
            )
            for e in self.entregas
            if e.time_window_start and e.time_window_end
        ]
        if not janelas:
            return None

        inicio = max(j[0] for j in janelas)
        fim = min(j[1] for j in janelas)
        return (inicio, fim) if inicio < fim else None

    def janela_conflitante(self) -> bool:
        tem_janela = any(e.time_window_start and e.time_window_end for e in self.entregas)
        return tem_janela and self.janela() is None


def _normalizar(texto: str | None) -> str:
    if not texto:
        return ""
    t = unicodedata.normalize("NFKD", texto)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", t.lower()).split())




def _chave_de_agrupamento(entrega: Delivery, precisao: int) -> str:
    """Decide o que significa "mesmo lugar" para esta entrega.

    Quando a coordenada e confiavel — veio do numero do predio (EXATO) ou
    foi marcada a mao no mapa (MANUAL) — o criterio e a POSICAO, so ela.
    Duas entregas no mesmo ponto sao uma parada, mesmo que o endereco tenha
    sido digitado de formas diferentes ("Rua X, 100" e "Rua X, 100 apto 2",
    ou o mesmo cliente com duas compras). Quem estaciona uma vez estaciona
    uma vez.

    Quando a coordenada e grosseira — nivel de rua, bairro ou cidade — a
    posicao deixa de provar que e o mesmo lugar: varios enderecos distintos
    caem no mesmo ponto. Ai o endereco entra na chave, e o agrupamento fica
    conservador. Errar para menos aqui custa uma parada a mais na rota;
    errar para mais juntaria entregas que estao a quarteiroes de distancia.
    """
    lat = round(float(entrega.latitude), precisao)
    lon = round(float(entrega.longitude), precisao)

    if precisao_confiavel(entrega):
        return f"{lat}|{lon}"
    return f"{lat}|{lon}|{_normalizar(entrega.address)[:60]}"


def agrupar(
    entregas: list[Delivery], *, precisao: int = PRECISAO_AGRUPAMENTO
) -> list[ParadaAgrupada]:
    """Agrupa entregas que acontecem no mesmo lugar.

    O criterio esta em `_chave_de_agrupamento`: posicao quando a coordenada
    e confiavel, posicao mais endereco quando nao e.

    Entregas com janelas de horario incompativeis sao separadas em paradas
    distintas, mesmo no mesmo endereco: juntar criaria uma parada impossivel
    e o solver diria apenas "sem solucao".
    """
    grupos: dict[str, ParadaAgrupada] = {}

    for entrega in entregas:
        if entrega.latitude is None or entrega.longitude is None:
            continue  # quem chama ja recusou essas; aqui e defesa

        lat = round(float(entrega.latitude), precisao)
        lon = round(float(entrega.longitude), precisao)
        chave = _chave_de_agrupamento(entrega, precisao)

        grupo = grupos.get(chave)
        if grupo is None:
            grupo = ParadaAgrupada(
                chave=chave,
                latitude=lat,
                longitude=lon,
                rotulo=entrega.recipient_name or entrega.address or f"Entrega {entrega.id}",
                endereco=entrega.address,
            )
            grupos[chave] = grupo

        grupo.entregas.append(entrega)

        # Se juntar esta entrega tornou a janela impossivel, ela sai para
        # uma parada propria — mesmo endereco, visita separada.
        if grupo.janela_conflitante():
            grupo.entregas.pop()
            avulsa = ParadaAgrupada(
                chave=f"{chave}#{entrega.id}",
                latitude=lat,
                longitude=lon,
                rotulo=entrega.recipient_name or entrega.address or f"Entrega {entrega.id}",
                endereco=entrega.address,
                entregas=[entrega],
            )
            grupos[avulsa.chave] = avulsa
            logger.info(
                "Entrega %s separada em parada propria: janela incompativel com o grupo.",
                entrega.id,
            )

    return list(grupos.values())


def desagrupar_excedentes(
    paradas: list[ParadaAgrupada],
    *,
    maior_peso_kg: float | None,
    maior_volume_m3: float | None,
) -> tuple[list[ParadaAgrupada], list[str]]:
    """Separa paradas cuja carga somada nao cabe em nenhum veiculo.

    Sem isso, uma parada gorda tornaria o problema inviavel e a resposta
    seria "sem solucao", sem dizer que o motivo foi juntar cinco entregas no
    mesmo endereco. Melhor visitar o mesmo lugar duas vezes do que nao
    planejar o dia.
    """
    resultado: list[ParadaAgrupada] = []
    avisos: list[str] = []

    for parada in paradas:
        excede_peso = maior_peso_kg is not None and parada.peso_kg > maior_peso_kg
        excede_volume = maior_volume_m3 is not None and parada.volume_m3 > maior_volume_m3

        if (excede_peso or excede_volume) and len(parada.entregas) > 1:
            avisos.append(
                f"{parada.rotulo}: as {len(parada.entregas)} entregas somadas nao cabem "
                "em um unico veiculo; foram divididas em visitas separadas."
            )
            for entrega in parada.entregas:
                resultado.append(
                    ParadaAgrupada(
                        chave=f"{parada.chave}#{entrega.id}",
                        latitude=parada.latitude,
                        longitude=parada.longitude,
                        rotulo=parada.rotulo,
                        endereco=parada.endereco,
                        entregas=[entrega],
                    )
                )
        else:
            resultado.append(parada)

    return resultado, avisos
