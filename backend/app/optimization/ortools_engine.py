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

MAIS DE UMA VIAGEM. Com `max_viagens` > 1, cada veiculo vira N "viagens" no
modelo — copias dele que saem e voltam a base. A viagem k+1 so pode sair
depois de a k voltar mais o tempo de recarga, e todas dividem a mesma
jornada (o tempo do modelo e um relogio so, contado do inicio do turno).
A recarga devolve a capacidade inteira: cada viagem sai com o caminhao
cheio. Uma viagem que nao e usada nao atrasa nada — a recarga so conta
quando a viagem seguinte existe.
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
    RecargaResolvida,
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
        # Cada veiculo do modelo e uma VIAGEM: (indice do veiculo, numero).
        self._viagens = [
            (v, numero)
            for v in range(len(pedido.veiculos))
            for numero in range(1, max(1, pedido.opcoes.max_viagens) + 1)
        ]
        k = len(self._viagens)

        gestor = pywrapcp.RoutingIndexManager(n, k, 0)
        modelo = pywrapcp.RoutingModel(gestor)

        self._configurar_custo_de_tempo(modelo, gestor, pedido)
        self._configurar_jornada(modelo, gestor, pedido)
        self._configurar_capacidades(modelo, gestor, pedido)
        self._configurar_max_paradas(modelo, gestor, pedido)
        self._configurar_equipe(modelo, gestor, pedido)
        self._configurar_janelas(modelo, gestor, pedido)
        self._encadear_viagens(modelo, pedido)

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
        """O custo do arco e o tempo de servico na ORIGEM + a viagem.

        Incluir o servico no arco e o que faz o solver entender que uma
        instalacao de duas horas custa mais que dez minutos de deslocamento.
        Sem isso ele otimizaria quilometragem e montaria rotas que nao cabem
        no dia.

        O servico e o da ORIGEM, nao o do destino, e isso muda o significado
        do tempo acumulado em cada parada. Com o servico do destino -- como
        estava --, o acumulado era a hora em que o servico TERMINA:

        - a "chegada" gravada no plano saia atrasada exatamente o tempo de
          servico da parada (entrega a 1 km da base prevista para 66 min
          depois da saida: 6 de estrada + 60 de instalacao);
        - a janela do cliente restringia o FIM do servico, nao a chegada: um
          cliente que recebe das 8h as 10h, com instalacao de 1 h, podia
          receber o caminhao as 7h.

        Com o servico da origem, o acumulado e a hora de CHEGADA, e a janela
        vale para a chegada. O custo total da rota nao muda: cada parada
        visitada e origem de exatamente um arco.
        """

        def custo(de_indice, para_indice):
            de = gestor.IndexToNode(de_indice)
            para = gestor.IndexToNode(para_indice)
            servico = 0 if de == 0 else pedido.paradas[de - 1].tempo_servico_s
            return servico + pedido.duracoes[de][para]

        self._callback_tempo = modelo.RegisterTransitCallback(custo)
        modelo.SetArcCostEvaluatorOfAllVehicles(self._callback_tempo)

    def _veiculo(self, pedido, viagem_idx: int):
        return pedido.veiculos[self._viagens[viagem_idx][0]]

    def _configurar_jornada(self, modelo, gestor, pedido) -> None:
        """Limita cada rota a duracao do turno do veiculo.

        O limite e sobre o RELOGIO (segundos desde o inicio do turno), nao
        sobre a duracao de cada viagem: a segunda viagem de um veiculo
        comeca onde a primeira terminou, e as duas cabem na mesma jornada.
        """
        modelo.AddDimensionWithVehicleCapacity(
            self._callback_tempo,
            HORIZONTE_S,  # espera permitida (usada pelas janelas)
            [self._veiculo(pedido, i).jornada_s for i in range(len(self._viagens))],
            False,  # nao forca inicio em zero: o turno comeca quando comeca
            "Tempo",
        )

    def _encadear_viagens(self, modelo, pedido) -> None:
        """Viagem k+1 sai depois de a k voltar e recarregar.

        A recarga multiplica a ATIVIDADE da viagem seguinte: se ela nao for
        usada, nao ha recarga, e a viagem vazia nao empurra o relogio. E a
        viagem k+1 so e usada se a k for — sem isso, "viagem 1 vazia e
        viagem 2 cheia" seria a mesma solucao com outro nome, e o solver
        perderia tempo com ela.
        """
        if pedido.opcoes.max_viagens <= 1:
            return
        tempo = modelo.GetDimensionOrDie("Tempo")
        solver = modelo.solver()
        for i in range(1, len(self._viagens)):
            (v_ant, _), (v, numero) = self._viagens[i - 1], self._viagens[i]
            if v != v_ant or numero == 1:
                continue
            ativa = modelo.ActiveVehicleVar(i)
            solver.Add(
                tempo.CumulVar(modelo.Start(i))
                >= tempo.CumulVar(modelo.End(i - 1)) + ativa * pedido.opcoes.recarga_s
            )
            solver.Add(ativa <= modelo.ActiveVehicleVar(i - 1))
        # Cada viagem sai assim que pode: sem isto, a hora de saida da
        # segunda viagem ficaria em qualquer valor que cumprisse as regras.
        for i in range(len(self._viagens)):
            modelo.AddVariableMinimizedByFinalizer(tempo.CumulVar(modelo.Start(i)))

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
            # Cada viagem sai com o caminhao cheio: a capacidade vale por
            # viagem, e a carga comeca em zero em cada uma.
            modelo.AddDimensionWithVehicleCapacity(
                cb,
                0,
                [
                    round(capacidades[v] * escala) if capacidades[v] is not None else 10**9
                    for v, _ in self._viagens
                ],
                True,
                nome,
            )

    def _configurar_max_paradas(self, modelo, gestor, pedido) -> None:
        if all(v.max_paradas is None for v in pedido.veiculos):
            return

        def conta(indice):
            return 0 if gestor.IndexToNode(indice) == 0 else 1

        cb = modelo.RegisterUnaryTransitCallback(conta)
        # Por viagem, como a capacidade: e quanto cabe no caminhao de uma vez.
        modelo.AddDimensionWithVehicleCapacity(
            cb,
            0,
            [
                self._veiculo(pedido, i).max_paradas
                if self._veiculo(pedido, i).max_paradas is not None
                else 10**6
                for i in range(len(self._viagens))
            ],
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
                i
                for i in range(len(self._viagens))
                if self._veiculo(pedido, i).tamanho_equipe >= parada.demanda.equipe
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
        for v in range(len(self._viagens)):
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
            rota: RotaResolvida | None = None
            ordem = 0
            numero_da_viagem = 0

            for i, (dono, _) in enumerate(self._viagens):
                if dono != v:
                    continue
                trechos = self._ler_viagem(modelo, gestor, solucao, pedido, i)
                if not trechos:
                    # Viagem vazia nao vira nada: nem rota, nem recarga.
                    continue
                numero_da_viagem += 1
                saida = solucao.Value(dimensao_tempo.CumulVar(modelo.Start(i)))
                chegada = solucao.Value(dimensao_tempo.CumulVar(modelo.End(i)))
                ultimo_no = trechos[-1][0]

                if rota is None:
                    rota = RotaResolvida(
                        veiculo_id=veiculo.id,
                        paradas=[],
                        distancia_total_m=0,
                        duracao_total_s=0,
                        carga_peso_kg=0.0,
                        carga_volume_m3=0.0,
                        saida_s=saida,
                    )
                else:
                    rota.recargas.append(
                        RecargaResolvida(
                            viagem=numero_da_viagem,
                            chegada_s=rota.chegada_base_s,
                            saida_s=saida,
                            distancia_do_anterior_m=rota.retorno_distancia_m,
                            duracao_do_anterior_s=rota.retorno_duracao_s,
                        )
                    )
                    rota.duracao_total_s += pedido.opcoes.recarga_s

                for no, indice, trecho_m, trecho_s in trechos:
                    parada = pedido.paradas[no - 1]
                    visitados.add(no)
                    ordem += 1
                    rota.paradas.append(
                        ParadaResolvida(
                            parada_id=parada.id,
                            ordem=ordem,
                            chegada_estimada_s=solucao.Value(dimensao_tempo.CumulVar(indice)),
                            distancia_do_anterior_m=trecho_m,
                            duracao_do_anterior_s=trecho_s,
                            viagem=numero_da_viagem,
                        )
                    )
                    rota.distancia_total_m += trecho_m
                    rota.duracao_total_s += trecho_s + parada.tempo_servico_s
                    rota.carga_peso_kg = round(
                        rota.carga_peso_kg + (parada.demanda.peso_kg or 0), 2
                    )
                    rota.carga_volume_m3 = round(
                        rota.carga_volume_m3 + (parada.demanda.volume_m3 or 0), 3
                    )

                rota.retorno_distancia_m = pedido.distancias[ultimo_no][0]
                rota.retorno_duracao_s = pedido.duracoes[ultimo_no][0]
                rota.distancia_total_m += rota.retorno_distancia_m
                rota.duracao_total_s += rota.retorno_duracao_s
                rota.chegada_base_s = chegada

            # Veiculo que nao recebeu parada nenhuma nao vira rota vazia no
            # planejamento — ele simplesmente nao sai.
            if rota is not None:
                rotas.append(rota)

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
                "viagens": sum(r.quantidade_viagens for r in rotas),
                "paradas_atendidas": len(visitados),
                "paradas_totais": len(pedido.paradas),
            },
        )

    @staticmethod
    def _ler_viagem(modelo, gestor, solucao, pedido, viagem_idx):
        """[(no, indice, metros do anterior, segundos do anterior)] da viagem."""
        trechos = []
        indice = modelo.Start(viagem_idx)
        while not modelo.IsEnd(indice):
            no = gestor.IndexToNode(indice)
            proximo = solucao.Value(modelo.NextVar(indice))
            no_proximo = gestor.IndexToNode(proximo)
            if no_proximo != 0:
                trechos.append(
                    (
                        no_proximo,
                        proximo,
                        pedido.distancias[no][no_proximo],
                        pedido.duracoes[no][no_proximo],
                    )
                )
            indice = proximo
        return trechos
