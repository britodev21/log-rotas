"""Planejamento de rotas: calcular, revisar, confirmar.

Este modulo e a costura entre geocodificacao, matriz, agrupamento e solver.
Ele nao implementa nenhum dos quatro — orquestra.

A regra que governa tudo aqui: **calcular nao muda a operacao**. O resultado
nasce como RASCUNHO, nenhuma entrega troca de status e nenhum motorista
recebe nada. So a confirmacao explicita do administrador transforma isso em
rota de verdade.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, time, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import (
    DeliveryStatus,
    MatrixSource,
    PlanStatus,
    Priority,
    RouteStatus,
    StopType,
)
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.models.base_location import BaseLocation
from app.models.delivery import Delivery
from app.models.driver import Driver
from app.models.route import Route, RoutePlan, RouteStop, RouteStopDelivery
from app.models.user import User
from app.models.vehicle import Vehicle
from app.optimization import (
    Demanda,
    JanelaHorario,
    OpcoesOtimizacao,
    OptimizationRequest,
    ParadaPlanejada,
    VeiculoDisponivel,
    resolver,
)
from app.repositories.company_settings_repository import CompanySettingsRepository
from app.repositories.delivery_repository import DeliveryRepository
from app.routing import Ponto, RoutingService, transito
from app.routing.base import Matriz
from app.routing.matriz_transito import MatrizComTransito
from app.schemas.planning import CalcularRequest, ConfirmarRequest
from app.services import precisao, status_machine
from app.services.delivery_service import DeliveryService
from app.services.stop_grouping import agrupar, desagrupar_excedentes

logger = logging.getLogger(__name__)

PESO_PRIORIDADE = {
    Priority.URGENTE.value: 0,
    Priority.ALTA.value: 1,
    Priority.NORMAL.value: 2,
    Priority.BAIXA.value: 3,
}


class PlanningService:
    def __init__(self, session: Session, routing: RoutingService | None = None) -> None:
        self.session = session
        self.entregas = DeliveryRepository(session)
        self.config = CompanySettingsRepository(session)
        self.routing = routing or RoutingService()
        self.matriz_transito = MatrizComTransito(session)

    # ------------------------------------------------------------------ #
    # Calcular
    # ------------------------------------------------------------------ #
    def calcular(self, payload: CalcularRequest, *, actor: User | None = None) -> RoutePlan:
        base = self._base(payload.base_id)
        entregas = self._entregas(payload)
        veiculos = self._veiculos(payload.vehicle_ids)
        motoristas = self._motoristas(payload.driver_ids)

        avisos: list[str] = []

        # 1. Agrupar entregas que acontecem no mesmo lugar.
        paradas = agrupar(entregas)

        maior_peso = max(
            (float(v.capacity_weight_kg) for v in veiculos if v.capacity_weight_kg),
            default=None,
        )
        maior_volume = max(
            (float(v.capacity_volume_m3) for v in veiculos if v.capacity_volume_m3),
            default=None,
        )
        paradas, avisos_divisao = desagrupar_excedentes(
            paradas, maior_peso_kg=maior_peso, maior_volume_m3=maior_volume
        )
        avisos.extend(avisos_divisao)

        if not paradas:
            raise ValidationError("Nenhuma entrega valida para planejar.")

        tempo_padrao = self._tempo_padrao_min()
        inicio_turno_s = self._segundos(payload.inicio_turno)
        momento_inicio = self._momento_inicio(payload.date, inicio_turno_s)

        # 2. Matriz: base na posicao 0, paradas em seguida. Primeiro a da rua
        # livre (OSRM, gratis); depois, se houver, a do transito previsto
        # para o dia e a hora do turno.
        pontos = [Ponto("base", float(base.latitude), float(base.longitude), base.name)]
        pontos += [Ponto(p.chave, p.latitude, p.longitude, p.rotulo) for p in paradas]
        livre = self.routing.matriz(pontos)
        matriz, info_transito = self._com_transito(
            livre, momento_inicio, pedido=payload.considerar_transito
        )
        avisos.extend(matriz.avisos)

        # 3. Montar o pedido para o solver.

        pedido = OptimizationRequest(
            deposito=ParadaPlanejada(
                id="base",
                latitude=float(base.latitude),
                longitude=float(base.longitude),
                rotulo=base.name,
                tempo_servico_s=0,
            ),
            paradas=[
                ParadaPlanejada(
                    id=p.chave,
                    latitude=p.latitude,
                    longitude=p.longitude,
                    rotulo=p.rotulo,
                    tempo_servico_s=p.tempo_servico_s(tempo_padrao),
                    demanda=Demanda(
                        peso_kg=p.peso_kg or None,
                        volume_m3=p.volume_m3 or None,
                        comprimento_m=p.comprimento_m or None,
                        equipe=p.equipe,
                    ),
                    janela=self._janela(p, inicio_turno_s),
                    prioridade=PESO_PRIORIDADE.get(p.prioridade, 2),
                    entregas=tuple(str(i) for i in p.ids),
                )
                for p in paradas
            ],
            veiculos=[
                VeiculoDisponivel(
                    id=str(v.id),
                    rotulo=v.name,
                    capacidade_peso_kg=float(v.capacity_weight_kg)
                    if v.capacity_weight_kg
                    else None,
                    capacidade_volume_m3=float(v.capacity_volume_m3)
                    if v.capacity_volume_m3
                    else None,
                    capacidade_comprimento_m=float(v.capacity_length_m)
                    if v.capacity_length_m
                    else None,
                    max_paradas=v.max_stops,
                    tamanho_equipe=v.crew_size,
                )
                for v in veiculos
            ],
            duracoes=matriz.duracoes,
            distancias=matriz.distancias,
            opcoes=OpcoesOtimizacao(
                limite_tempo_s=payload.limite_tempo_s,
                permitir_dispensar=payload.permitir_dispensar,
                inicio_turno_s=inicio_turno_s,
            ),
        )

        # 4. Resolver.
        resultado = resolver(pedido)

        if not resultado.sucesso:
            # Falha explicita, com o motivo. Nunca uma ordenacao qualquer
            # apresentada como se fosse otimizacao.
            raise ConflictError(
                resultado.mensagem or "Nao foi possivel montar o planejamento.",
                details={
                    "status_solver": resultado.status.value,
                    "estatisticas": resultado.estatisticas,
                    "avisos": avisos,
                },
            )

        if info_transito["considerado"]:
            # Quanto o transito pesou nas pernas que o plano de fato usa: e o
            # numero que responde "o que muda por considerar o transito?".
            info_transito["estrada_livre_s"] = self._estrada(resultado, livre)
            info_transito["estrada_transito_s"] = self._estrada(resultado, matriz)

        # 5. Persistir como RASCUNHO.
        plano = self._persistir(
            payload=payload,
            base=base,
            paradas=paradas,
            veiculos=veiculos,
            motoristas=motoristas,
            matriz=matriz,
            resultado=resultado,
            avisos=avisos,
            momento_inicio=momento_inicio,
            info_transito=info_transito,
            actor=actor,
        )

        self.session.commit()
        logger.info(
            "Plano %s calculado: %s rotas, %s dispensadas, fonte %s.",
            plano.id,
            len(resultado.rotas),
            len(resultado.dispensadas),
            matriz.source.value,
        )
        return plano

    # ------------------------------------------------------------------ #
    # Confirmar / descartar
    # ------------------------------------------------------------------ #
    def confirmar(
        self, plano_id: int, payload: ConfirmarRequest, *, actor: User | None = None
    ) -> RoutePlan:
        """Transforma o rascunho em operacao de verdade.

        So aqui as entregas mudam de status e as rotas ficam disponiveis
        para o motorista. Antes disso, nada do que foi calculado afeta o dia.
        """
        plano = self.get(plano_id)
        status_machine.exigir("plano", plano.status, PlanStatus.CONFIRMADO.value)

        servico_entregas = DeliveryService(self.session)

        for rota in plano.routes:
            if rota.id in payload.atribuicoes:
                rota.driver_id = payload.atribuicoes[rota.id]

            if rota.driver_id is None:
                raise ValidationError(
                    f"A rota do veiculo {rota.vehicle.name} esta sem motorista. "
                    "Atribua um motorista a cada rota antes de confirmar."
                )

            status_machine.exigir("rota", rota.status, RouteStatus.PLANEJADA.value)
            rota.status = RouteStatus.PLANEJADA.value

            for parada in rota.stops:
                for item in parada.items:
                    entrega = item.delivery
                    status_machine.exigir(
                        "entrega", entrega.status, DeliveryStatus.PLANEJADA.value
                    )
                    anterior = entrega.status
                    entrega.status = DeliveryStatus.PLANEJADA.value
                    item.status = DeliveryStatus.PLANEJADA.value
                    servico_entregas._registrar(
                        entrega,
                        anterior,
                        DeliveryStatus.PLANEJADA.value,
                        actor=actor,
                        route_stop_id=parada.id,
                    )

        plano.status = PlanStatus.CONFIRMADO.value
        plano.confirmed_at = datetime.now(UTC)

        self.session.commit()
        logger.info("Plano %s confirmado com %s rotas.", plano.id, len(plano.routes))
        return plano

    def descartar(self, plano_id: int) -> RoutePlan:
        """Joga fora um rascunho.

        As entregas nao precisam voltar de status porque nunca sairam de
        PENDENTE — essa e justamente a vantagem de o calculo nao mexer na
        operacao.
        """
        plano = self.get(plano_id)
        status_machine.exigir("plano", plano.status, PlanStatus.DESCARTADO.value)

        plano.status = PlanStatus.DESCARTADO.value
        for rota in plano.routes:
            rota.status = RouteStatus.CANCELADA.value

        self.session.commit()
        return plano

    # ------------------------------------------------------------------ #
    # Leitura
    # ------------------------------------------------------------------ #
    def get(self, plano_id: int) -> RoutePlan:
        plano = self.session.get(RoutePlan, plano_id)
        if plano is None:
            raise NotFoundError("Planejamento nao encontrado.")
        return plano

    def listar(self, *, data: date | None = None, status: str | None = None) -> list[RoutePlan]:
        stmt = select(RoutePlan).order_by(RoutePlan.created_at.desc())
        if data is not None:
            stmt = stmt.where(RoutePlan.date == data)
        if status:
            stmt = stmt.where(RoutePlan.status == status)
        return list(self.session.scalars(stmt).unique())

    # ------------------------------------------------------------------ #
    # Apoio
    # ------------------------------------------------------------------ #
    def _base(self, base_id: int) -> BaseLocation:
        base = self.session.get(BaseLocation, base_id)
        if base is None:
            raise NotFoundError("Base nao encontrada.")
        if not base.active:
            raise ValidationError("A base selecionada esta inativa.")
        if base.latitude is None or base.longitude is None:
            raise ValidationError(
                f"A base {base.name} ainda nao tem coordenada. "
                "Geocodifique o endereco dela ou marque o ponto no mapa."
            )
        return base

    def _entregas(self, payload: CalcularRequest) -> list[Delivery]:
        if payload.delivery_ids:
            entregas = self.entregas.por_ids(payload.delivery_ids)
            faltando = set(payload.delivery_ids) - {e.id for e in entregas}
            if faltando:
                raise NotFoundError(
                    f"Entregas nao encontradas: {sorted(faltando)}",
                    details={"ids": sorted(faltando)},
                )
        else:
            entregas = self.entregas.pendentes_para_planejar(payload.date)

        if not entregas:
            raise ValidationError(
                "Nenhuma entrega pendente para esta data.",
                details={"data": payload.date.isoformat()},
            )

        nao_planejaveis = [e for e in entregas if e.status != DeliveryStatus.PENDENTE.value]
        if nao_planejaveis:
            raise ConflictError(
                "Algumas entregas selecionadas nao estao mais pendentes.",
                details={
                    "entregas": [{"id": e.id, "status": e.status} for e in nao_planejaveis[:20]]
                },
            )

        # Recusa explicita, com a lista. Ignorar em silencio faria entregas
        # sumirem do plano sem ninguem perceber — e elas so reapareceriam
        # quando o cliente ligasse cobrando.
        # A barreira nao e so "tem coordenada": e "a coordenada aponta o
        # lugar certo". Em Campo Grande o OpenStreetMap tem numero de porta
        # em cerca de 530 predios, entao o provedor resolve no nivel da RUA
        # quase sempre. Uma coordenada dessas colocada numa rota parece
        # perfeita — tem quilometragem, tem horario — e manda o caminhao
        # para qualquer ponto de uma avenida de 10 km.
        #
        # Planejar com pino aproximado e o que produz entrega errada, e
        # nenhum calculo posterior corrige isso. A regra vive em
        # app/services/precisao.py, junto com a medicao que a justifica.
        imprecisas = [(e, precisao.motivo(e)) for e in entregas]
        imprecisas = [(e, m) for e, m in imprecisas if m is not None]
        if imprecisas:
            sem_ponto = sum(1 for _, m in imprecisas if m == "sem coordenada")
            aproximadas = len(imprecisas) - sem_ponto
            partes = []
            if sem_ponto:
                partes.append(f"{sem_ponto} sem coordenada")
            if aproximadas:
                partes.append(f"{aproximadas} com posicao aproximada")
            raise ValidationError(
                f"{len(imprecisas)} entrega(s) nao podem ser planejadas "
                f"({', '.join(partes)}). Marque o ponto exato na tela de "
                "Enderecos — uma vez por endereco, e ele nao e perguntado "
                "de novo.",
                details={
                    "entregas": [
                        {
                            "id": e.id,
                            "endereco": e.address,
                            "situacao": e.geocode_status,
                            "precisao": e.geocode_precision,
                            "motivo": m,
                        }
                        for e, m in imprecisas[:20]
                    ],
                    "total": len(imprecisas),
                },
            )

        return entregas

    def _veiculos(self, ids: list[int]) -> list[Vehicle]:
        veiculos = list(self.session.scalars(select(Vehicle).where(Vehicle.id.in_(ids))))
        if len(veiculos) != len(set(ids)):
            raise NotFoundError("Algum veiculo selecionado nao existe.")
        inativos = [v.name for v in veiculos if not v.active]
        if inativos:
            raise ValidationError(f"Veiculos inativos: {', '.join(inativos)}")
        return veiculos

    def _motoristas(self, ids: list[int]) -> list[Driver]:
        if not ids:
            return []
        motoristas = list(self.session.scalars(select(Driver).where(Driver.id.in_(ids))))
        inativos = [m.name for m in motoristas if not m.active]
        if inativos:
            raise ValidationError(f"Motoristas inativos: {', '.join(inativos)}")
        return motoristas

    def _tempo_padrao_min(self) -> int:
        config = self.config.get()
        return config.default_stop_service_minutes if config else 60

    def _com_transito(
        self, livre: Matriz, partida: datetime, *, pedido: bool
    ) -> tuple[Matriz, dict]:
        """A matriz com o transito previsto, ou a livre com o motivo de nao ser.

        Sem transito o plano continua valido — e o que o sistema fazia antes
        —, mas a tela diz que os tempos sao de rua livre e por que.
        """
        if not pedido:
            return livre, {"considerado": False, "motivo": "desligado neste calculo"}
        if not transito.disponivel():
            return livre, {"considerado": False, "motivo": "transito nao configurado"}
        try:
            matriz, resumo = self.matriz_transito.aplicar(livre, partida)
        except transito.TransitoIndisponivel as exc:
            logger.warning("Planejamento sem transito: %s", exc)
            livre.avisos.append(
                f"O transito nao foi considerado ({exc}). Os tempos de deslocamento "
                "sao de rua livre e tendem a ser otimistas."
            )
            return livre, {"considerado": False, "motivo": str(exc)}
        # `partida` e a hora usada; `partida_do_turno`, a pedida. Diferem quando
        # o turno ja comecou: o Google nao preve o passado, e vale o de agora.
        return matriz, {
            "considerado": True,
            **resumo.como_dict(),
            "partida_do_turno": partida.isoformat(),
        }

    @staticmethod
    def _estrada(resultado, matriz: Matriz) -> int:
        """Segundos de deslocamento das rotas montadas, segundo `matriz`."""
        total = 0
        for rota in resultado.rotas:
            sequencia = [0, *(matriz.indice(p.parada_id) for p in rota.paradas), 0]
            total += sum(
                matriz.duracoes[a][b] for a, b in pairwise(sequencia)
            )
        return total

    @staticmethod
    def _momento_inicio(dia: date, inicio_turno_s: int) -> datetime:
        # O turno e digitado em hora de Campo Grande. Ancorado em UTC -- como
        # estava -- "08:00" virava 04:00 local, e todo horario previsto do
        # plano saia quatro horas adiantado. Ficou invisivel ate a previsao
        # ao vivo comparar o plano com a posicao real e acusar 11 h de atraso
        # numa rota que tinha acabado de sair.
        return datetime.combine(
            dia,
            time(hour=inicio_turno_s // 3600, minute=(inicio_turno_s % 3600) // 60),
            tzinfo=ZoneInfo(get_settings().default_timezone),
        )

    @staticmethod
    def _segundos(hhmm: str) -> int:
        horas, minutos = hhmm.split(":")
        return int(horas) * 3600 + int(minutos) * 60

    @staticmethod
    def _janela(parada, inicio_turno_s: int) -> JanelaHorario | None:
        bruta = parada.janela()
        if bruta is None:
            return None
        inicio, fim = bruta
        # A dimensao de tempo do solver conta a partir do inicio do turno.
        return JanelaHorario(
            inicio_s=max(0, inicio - inicio_turno_s),
            fim_s=max(0, fim - inicio_turno_s),
        )

    # ------------------------------------------------------------------ #
    def _persistir(
        self,
        *,
        payload,
        base,
        paradas,
        veiculos,
        motoristas,
        matriz,
        resultado,
        avisos,
        momento_inicio,
        info_transito,
        actor,
    ) -> RoutePlan:
        por_chave = {p.chave: p for p in paradas}
        por_id_veiculo = {str(v.id): v for v in veiculos}

        plano = RoutePlan(
            base_id=base.id,
            date=payload.date,
            status=PlanStatus.RASCUNHO.value,
            matrix_source=matriz.source.value,
            solver=resultado.solver,
            solver_status=resultado.status.value,
            solver_time_ms=resultado.tempo_ms,
            total_distance_m=resultado.distancia_total_m,
            total_duration_s=resultado.duracao_total_s,
            created_by=actor.id if actor else None,
            params={
                "delivery_ids": payload.delivery_ids,
                "vehicle_ids": payload.vehicle_ids,
                "driver_ids": payload.driver_ids,
                "inicio_turno": payload.inicio_turno,
                "limite_tempo_s": payload.limite_tempo_s,
                "matriz": {
                    "fonte": matriz.source.value,
                    "estimada": matriz.estimada,
                    "detalhe": matriz.detalhe,
                },
                "transito": info_transito,
                "avisos": avisos,
                "estatisticas": resultado.estatisticas,
            },
            unassigned=[
                {
                    "delivery_ids": por_chave[d.parada_id].ids
                    if d.parada_id in por_chave
                    else [],
                    "rotulo": d.rotulo,
                    "motivo": d.motivo,
                }
                for d in resultado.dispensadas
            ],
        )
        self.session.add(plano)
        self.session.flush()

        for indice, rota_resolvida in enumerate(resultado.rotas):
            veiculo = por_id_veiculo[rota_resolvida.veiculo_id]
            motorista = motoristas[indice] if indice < len(motoristas) else None

            rota = Route(
                route_plan_id=plano.id,
                base_id=base.id,
                vehicle_id=veiculo.id,
                driver_id=motorista.id if motorista else None,
                date=payload.date,
                status=RouteStatus.RASCUNHO.value,
                sequence_in_day=1,
                total_distance_m=rota_resolvida.distancia_total_m,
                estimated_duration_s=rota_resolvida.duracao_total_s,
                planned_weight_kg=rota_resolvida.carga_peso_kg or None,
                planned_volume_m3=rota_resolvida.carga_volume_m3 or None,
            )
            self.session.add(rota)
            self.session.flush()

            # Saida da base.
            self.session.add(
                RouteStop(
                    route_id=rota.id,
                    stop_type=StopType.BASE_SAIDA.value,
                    trip_number=1,
                    sequence=0,
                    label=base.name,
                    address=base.address,
                    latitude=base.latitude,
                    longitude=base.longitude,
                    estimated_arrival=momento_inicio,
                )
            )

            coordenadas = [(float(base.latitude), float(base.longitude))]

            for resolvida in rota_resolvida.paradas:
                agrupada = por_chave[resolvida.parada_id]
                parada = RouteStop(
                    route_id=rota.id,
                    stop_type=StopType.ENTREGA.value,
                    trip_number=1,
                    sequence=resolvida.ordem,
                    label=agrupada.rotulo,
                    address=agrupada.endereco,
                    latitude=agrupada.latitude,
                    longitude=agrupada.longitude,
                    estimated_arrival=momento_inicio
                    + timedelta(seconds=resolvida.chegada_estimada_s),
                    distance_from_previous_m=resolvida.distancia_do_anterior_m,
                    duration_from_previous_s=resolvida.duracao_do_anterior_s,
                    service_time_s=agrupada.tempo_servico_s(self._tempo_padrao_min()),
                )
                self.session.add(parada)
                self.session.flush()

                for ordem, entrega in enumerate(agrupada.entregas, start=1):
                    self.session.add(
                        RouteStopDelivery(
                            route_stop_id=parada.id,
                            delivery_id=entrega.id,
                            sequence_in_stop=ordem,
                            status=DeliveryStatus.PLANEJADA.value,
                        )
                    )

                coordenadas.append((agrupada.latitude, agrupada.longitude))

            # Retorno a base.
            self.session.add(
                RouteStop(
                    route_id=rota.id,
                    stop_type=StopType.BASE_RETORNO.value,
                    trip_number=1,
                    sequence=len(rota_resolvida.paradas) + 1,
                    label=base.name,
                    address=base.address,
                    latitude=base.latitude,
                    longitude=base.longitude,
                )
            )
            coordenadas.append((float(base.latitude), float(base.longitude)))

            # Geometria do trajeto, para o mapa desenhar o caminho real em
            # vez de ligar os pontos com linha reta.
            rota.geometry = self._geometria(coordenadas)

        return plano

    def _geometria(self, coordenadas: list[tuple[float, float]]) -> str | None:
        if len(coordenadas) < 2:
            return None
        try:
            pontos = [Ponto(str(i), lat, lon) for i, (lat, lon) in enumerate(coordenadas)]
            return self.routing.trajeto(pontos).geometria
        except Exception as exc:  # pragma: no cover - o mapa e secundario
            # Falhar aqui nao pode derrubar o planejamento: sem geometria o
            # mapa desenha a ligacao reta entre paradas, tracejada.
            logger.warning("Nao foi possivel obter a geometria do trajeto: %s", exc)
            return None


def fonte_estimada(plano: RoutePlan) -> bool:
    return plano.matrix_source == MatrixSource.HAVERSINE.value
