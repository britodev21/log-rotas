"""Motor de otimizacao com Google OR-Tools.

Resolve um VRP com dimensao principal de TEMPO, e nao de quilometragem.

A escolha nao e arbitraria. A operacao e dentro de Campo Grande, com
deslocamentos de 10 a 25 minutos entre paradas. Se a entrega inclui
instalacao, o tempo de servico domina o tempo de estrada em ordem de
grandeza — e o que limita o dia da equipe nao e quanto ela roda, e quantos
servicos cabem no turno.

Minimizar quilometro numa operacao assim economiza centavos. Minimizar
tempo total, respeitando a jornada, economiza um dia de equipe.

A escolha tambem e robusta a estarmos errados: se a entrega for so
descarregar e ir embora, o tempo de servico vira dez minutos e o mesmo
modelo continua correto.
"""

from __future__ import annotations

import logging
import time

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.optimization.contracts import (
    OptimizationRequest,
    OptimizationResult,
    ParadaDispensada,
    ParadaResolvida,
    RotaResolvida,
    SolverStatus,
)

logger = logging.getLogger(__name__)

#: Custo de deixar uma parada de fora, por nivel de prioridade. Alto o
#: bastante para o solver so dispensar quando realmente nao couber, e
#: escalonado para que ele sacrifique uma entrega de prioridade BAIXA antes
#: de uma URGENTE.
PENALIDADE_POR_PRIORIDADE = {
    0: 4_000_000,  # URGENTE
    1: 1_500_000,  # ALTA
    2: 600_000,  # NORMAL
    3: 200_000,  # BAIXA
}

#: Teto da dimensao de tempo, em segundos. Precisa caber jornada + espera.
HORIZONTE_S = 24 * 3600


class OrToolsEngine:
    """Implementacao do motor de otimizacao."""

    nome = "ortools-vrp-tempo"

    def resolver(self, pedido: OptimizationRequest) -> OptimizationResult:
        erros = pedido.validar()
        if erros:
            # Recusa com explicacao, nao com "sem solucao". A diferenca e
            # quem consegue consertar o problema.
            return OptimizationResult(
                status=SolverStatus.INVIAVEL,
                mensagem=" ".join(erros),
                solver=self.nome,
                estatisticas={"erros_de_entrada": erros},
            )

        inicio = time.monotonic()
        n = len(pedido.paradas) + 1  # +1 pelo deposito
        k = len(pedido.veiculos)

        gestor = pywrapcp.RoutingIndexManager(n, k, 0)
        modelo = pywrapcp.RoutingModel(gestor)

        self._configurar_custo_de_tempo(modelo, gestor, pedido)
        self._configurar_jornada(modelo, gestor, pedido)
        self._configurar_capacidades(modelo, gestor, pedido)
        self._configurar_max_paradas(modelo, gestor, pedido)
        self._configurar_equipe(modelo, gestor, pedido)
        self._configurar_janelas(modelo, gestor, pedido)

        if pedido.opcoes.permitir_dispensar:
            self._permitir_dispensar(modelo, gestor, pedido)

        solucao = modelo.SolveWithParameters(self._parametros(pedido))
        decorrido = int((time.monotonic() - inicio) * 1000)

        if solucao is None:
            return OptimizationResult(
                status=SolverStatus.INVIAVEL,
                mensagem=(
                    "Nao foi possivel montar um planejamento com os veiculos e as "
                    "entregas selecionados. Verifique capacidade, jornada e janelas "
                    "de horario."
                ),
                solver=self.nome,
                tempo_ms=decorrido,
                estatisticas={"status_ortools": modelo.status()},
            )

        return self._montar_resultado(modelo, gestor, solucao, pedido, decorrido)

    # ------------------------------------------------------------------ #
    # Modelo
    # ------------------------------------------------------------------ #
    def _configurar_custo_de_tempo(self, modelo, gestor, pedido) -> None:
        """O custo do arco e tempo de viagem + tempo de servico no destino.

        Incluir o servico no arco e o que faz o solver entender que uma
        instalacao de duas horas custa mais que dez minutos de deslocamento.
        Sem isso ele otimizaria quilometragem e montaria rotas que nao cabem
        no dia.
        """

        def custo(de_indice, para_indice):
            de = gestor.IndexToNode(de_indice)
            para = gestor.IndexToNode(para_indice)
            servico = 0 if para == 0 else pedido.paradas[para - 1].tempo_servico_s
            return pedido.duracoes[de][para] + servico

        self._callback_tempo = modelo.RegisterTransitCallback(custo)
        modelo.SetArcCostEvaluatorOfAllVehicles(self._callback_tempo)

    def _configurar_jornada(self, modelo, gestor, pedido) -> None:
        """Limita cada rota a duracao do turno do veiculo."""
        modelo.AddDimensionWithVehicleCapacity(
            self._callback_tempo,
            HORIZONTE_S,  # espera permitida (usada pelas janelas)
            [v.jornada_s for v in pedido.veiculos],
            False,  # nao forca inicio em zero: o turno comeca quando comeca
            "Tempo",
        )

    def _configurar_capacidades(self, modelo, gestor, pedido) -> None:
        """Peso e volume, cada um como sua propria dimensao.

        Criadas SOMENTE quando existe demanda e capacidade. Inventar limite
        onde nao ha dado seria restringir o planejamento por engano.
        """
        dimensoes = [
            ("Peso", lambda p: p.demanda.peso_kg, lambda v: v.capacidade_peso_kg, 100),
            ("Volume", lambda p: p.demanda.volume_m3, lambda v: v.capacidade_volume_m3, 1000),
        ]

        for nome, pega_demanda, pega_capacidade, escala in dimensoes:
            capacidades = [pega_capacidade(v) for v in pedido.veiculos]
            demandas = [pega_demanda(p) for p in pedido.paradas]

            if all(c is None for c in capacidades) or all(d is None for d in demandas):
                continue

            def callback(indice, pega=pega_demanda, mult=escala):
                no = gestor.IndexToNode(indice)
                if no == 0:
                    return 0
                valor = pega(pedido.paradas[no - 1]) or 0
                # OR-Tools trabalha com inteiros: a escala preserva as casas
                # decimais que um arredondamento jogaria fora.
                return round(valor * mult)

            cb = modelo.RegisterUnaryTransitCallback(callback)
            modelo.AddDimensionWithVehicleCapacity(
                cb,
                0,
                [round(c * escala) if c is not None else 10**9 for c in capacidades],
                True,
                nome,
            )

    def _configurar_max_paradas(self, modelo, gestor, pedido) -> None:
        if all(v.max_paradas is None for v in pedido.veiculos):
            return

        def conta(indice):
            return 0 if gestor.IndexToNode(indice) == 0 else 1

        cb = modelo.RegisterUnaryTransitCallback(conta)
        modelo.AddDimensionWithVehicleCapacity(
            cb,
            0,
            [v.max_paradas if v.max_paradas is not None else 10**6 for v in pedido.veiculos],
            True,
            "Paradas",
        )

    def _configurar_equipe(self, modelo, gestor, pedido) -> None:
        """Parada que exige equipe maior so pode ir em veiculo que a leva.

        Diferente de capacidade: equipe nao se acumula ao longo da rota. E
        uma restricao de compatibilidade entre parada e veiculo, resolvida
        proibindo os veiculos que nao atendem.
        """
        exigem_mais = [
            (i, p) for i, p in enumerate(pedido.paradas, start=1) if p.demanda.equipe > 1
        ]
        if not exigem_mais:
            return

        for no, parada in exigem_mais:
            permitidos = [
                v
                for v, veiculo in enumerate(pedido.veiculos)
                if veiculo.tamanho_equipe >= parada.demanda.equipe
            ]
            modelo.VehicleVar(gestor.NodeToIndex(no)).SetValues(permitidos)

    def _configurar_janelas(self, modelo, gestor, pedido) -> None:
        com_janela = [(i, p) for i, p in enumerate(pedido.paradas, start=1) if p.janela]
        if not com_janela:
            return

        dimensao = modelo.GetDimensionOrDie("Tempo")
        for no, parada in com_janela:
            indice = gestor.NodeToIndex(no)
            dimensao.CumulVar(indice).SetRange(parada.janela.inicio_s, parada.janela.fim_s)

        # O inicio de cada veiculo tambem precisa estar dentro do horizonte,
        # senao o solver nao consegue posicionar a primeira parada.
        for v in range(len(pedido.veiculos)):
            dimensao.CumulVar(modelo.Start(v)).SetRange(0, HORIZONTE_S)
            modelo.AddVariableMinimizedByFinalizer(dimensao.CumulVar(modelo.Start(v)))
            modelo.AddVariableMinimizedByFinalizer(dimensao.CumulVar(modelo.End(v)))

    def _permitir_dispensar(self, modelo, gestor, pedido) -> None:
        for i, parada in enumerate(pedido.paradas, start=1):
            penalidade = PENALIDADE_POR_PRIORIDADE.get(parada.prioridade, 600_000)
            modelo.AddDisjunction([gestor.NodeToIndex(i)], penalidade)

    def _parametros(self, pedido):
        p = pywrapcp.DefaultRoutingSearchParameters()
        # PATH_CHEAPEST_ARC monta uma solucao inicial rapidamente;
        # GUIDED_LOCAL_SEARCH e quem de fato melhora, trocando paradas entre
        # veiculos e reordenando. Sem a segunda etapa isto seria apenas uma
        # heuristica gulosa — que e exatamente o que o projeto se recusa a
        # chamar de otimizacao.
        p.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        p.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        p.time_limit.FromSeconds(pedido.opcoes.limite_tempo_s)
        p.log_search = False
        return p

    # ------------------------------------------------------------------ #
    # Leitura da solucao
    # ------------------------------------------------------------------ #
    def _montar_resultado(
        self, modelo, gestor, solucao, pedido, decorrido
    ) -> OptimizationResult:
        dimensao_tempo = modelo.GetDimensionOrDie("Tempo")
        rotas: list[RotaResolvida] = []
        visitados: set[int] = set()

        for v, veiculo in enumerate(pedido.veiculos):
            indice = modelo.Start(v)
            paradas: list[ParadaResolvida] = []
            distancia = 0
            duracao = 0
            peso = 0.0
            volume = 0.0
            ordem = 0

            while not modelo.IsEnd(indice):
                no = gestor.IndexToNode(indice)
                proximo = solucao.Value(modelo.NextVar(indice))
                no_proximo = gestor.IndexToNode(proximo)

                trecho_m = pedido.distancias[no][no_proximo]
                trecho_s = pedido.duracoes[no][no_proximo]
                distancia += trecho_m
                duracao += trecho_s

                if no_proximo != 0:
                    parada = pedido.paradas[no_proximo - 1]
                    visitados.add(no_proximo)
                    ordem += 1
                    paradas.append(
                        ParadaResolvida(
                            parada_id=parada.id,
                            ordem=ordem,
                            chegada_estimada_s=solucao.Value(dimensao_tempo.CumulVar(proximo)),
                            distancia_do_anterior_m=trecho_m,
                            duracao_do_anterior_s=trecho_s,
                        )
                    )
                    duracao += parada.tempo_servico_s
                    peso += parada.demanda.peso_kg or 0
                    volume += parada.demanda.volume_m3 or 0

                indice = proximo

            # Veiculo que nao recebeu parada nenhuma nao vira rota vazia no
            # planejamento — ele simplesmente nao sai.
            if paradas:
                rotas.append(
                    RotaResolvida(
                        veiculo_id=veiculo.id,
                        paradas=paradas,
                        distancia_total_m=distancia,
                        duracao_total_s=duracao,
                        carga_peso_kg=round(peso, 2),
                        carga_volume_m3=round(volume, 3),
                    )
                )

        dispensadas = [
            ParadaDispensada(
                parada_id=p.id,
                rotulo=p.rotulo,
                motivo=(
                    "Nao coube nos veiculos disponiveis dentro da jornada, da "
                    "capacidade ou da janela de horario."
                ),
            )
            for i, p in enumerate(pedido.paradas, start=1)
            if i not in visitados
        ]

        status = SolverStatus.OTIMO if not dispensadas else SolverStatus.VIAVEL
        mensagem = (
            f"{len(rotas)} rota(s) montada(s)."
            if not dispensadas
            else (
                f"{len(rotas)} rota(s) montada(s); "
                f"{len(dispensadas)} parada(s) ficaram de fora."
            )
        )

        return OptimizationResult(
            status=status,
            rotas=rotas,
            dispensadas=dispensadas,
            mensagem=mensagem,
            solver=self.nome,
            tempo_ms=decorrido,
            estatisticas={
                "veiculos_usados": len(rotas),
                "veiculos_disponiveis": len(pedido.veiculos),
                "paradas_atendidas": len(visitados),
                "paradas_totais": len(pedido.paradas),
            },
        )
