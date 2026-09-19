import { useCallback, useEffect, useRef, useState } from "react";
import {
  CircleDashed,
  MapPinOff,
  Package,
  PackageCheck,
  PackageX,
  Route as RouteIcon,
  Truck,
  Users,
} from "lucide-react";
import { Link } from "react-router-dom";

import { mensagemDeErro } from "../../api/client";
import { painel as api } from "../../api/operacao";
import {
  AjustarLimites,
  MapPanel,
  MarcadorBase,
  MarcadoresEntregas,
  ParadasDaRota,
  TrajetoRota,
  corDaRota,
} from "../../components/map";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  KpiCard,
  PageHeader,
  SkeletonCard,
  SkeletonMap,
} from "../../components/ui";
import { useAuth } from "../../hooks/useAuth";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useTheme } from "../../hooks/useTheme";
import { distancia, duracao, hora } from "../../utils/formato";
import "./admin.css";

/** Intervalo do polling. 15s dá sensação de tempo real numa operação com
 *  poucos motoristas, sem transformar o painel aberto num gerador de carga. */
const INTERVALO_MS = 15000;

function saudacao() {
  const h = new Date().getHours();
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}

export function Dashboard() {
  useDocumentTitle("Painel");
  const { usuario } = useAuth();
  const { tema } = useTheme();

  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState("");
  const [atualizadoEm, setAtualizadoEm] = useState(null);
  const [rotaSelecionada, setRotaSelecionada] = useState(null);
  const primeiraCarga = useRef(true);

  const carregar = useCallback(async () => {
    try {
      setDados(await api.hoje());
      setErro("");
      setAtualizadoEm(new Date());
    } catch (e) {
      console.error("Falha ao carregar o painel", e);
      // Falha durante o polling não apaga a tela: manter o último estado
      // conhecido é mais útil do que um erro no lugar dos números.
      if (primeiraCarga.current) {
        setErro(mensagemDeErro(e, "Não foi possível carregar o painel."));
      }
    } finally {
      primeiraCarga.current = false;
    }
  }, []);

  useEffect(() => {
    carregar();
    const id = setInterval(carregar, INTERVALO_MS);
    return () => clearInterval(id);
  }, [carregar]);

  const primeiroNome = usuario?.name?.split(" ")[0] ?? "";

  if (erro && !dados) {
    return (
      <>
        <PageHeader titulo={`${saudacao()}, ${primeiroNome}`} />
        <Card>
          <ErrorState mensagem={erro} aoTentarNovamente={carregar} />
        </Card>
      </>
    );
  }

  if (!dados) {
    return (
      <>
        <PageHeader titulo={`${saudacao()}, ${primeiroNome}`} />
        <div className="kpis">
          {[0, 1, 2, 3].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
        <SkeletonMap altura={420} />
      </>
    );
  }

  const { entregas, rotas, rotas_ativas: ativas } = dados;
  const semOperacao = entregas.total === 0 && rotas.total === 0;

  const pontosMapa = [
    ...dados.bases.map((b) => [b.latitude, b.longitude]),
    ...dados.entregas_no_mapa.map((e) => [e.latitude, e.longitude]),
  ];

  return (
    <>
      <PageHeader
        titulo={`${saudacao()}, ${primeiroNome}`}
        descricao={new Intl.DateTimeFormat("pt-BR", {
          weekday: "long",
          day: "numeric",
          month: "long",
        }).format(new Date())}
        acoes={
          atualizadoEm && (
            <span className="texto-3">Atualizado às {hora(atualizadoEm.toISOString())}</span>
          )
        }
      />

      {entregas.sem_coordenada > 0 && (
        <Alert
          tom="atencao"
          titulo={`${entregas.sem_coordenada} entrega(s) sem coordenada`}
          acao={
            <Link to="/admin/enderecos">
              <Button variante="secundario" tamanho="sm">
                Resolver
              </Button>
            </Link>
          }
        >
          Elas não podem ser planejadas. É o que trava o planejamento do dia.
        </Alert>
      )}

      <div className="kpis anima-lista">
        <KpiCard
          rotulo="Entregas hoje"
          valor={entregas.total}
          contexto={`${entregas.pendentes} pendente(s)`}
          icone={Package}
          tom="marca"
        />
        <KpiCard
          rotulo="Em rota"
          valor={entregas.em_rota}
          contexto={
            rotas.motoristas_em_operacao > 0
              ? `${rotas.motoristas_em_operacao} motorista(s) na rua`
              : "ninguém na rua"
          }
          icone={Truck}
          tom="atencao"
        />
        <KpiCard
          rotulo="Concluídas"
          valor={entregas.entregues}
          contexto={
            entregas.total > 0
              ? `${Math.round((entregas.entregues / entregas.total) * 100)}% do dia`
              : "—"
          }
          icone={PackageCheck}
          tom="sucesso"
        />
        <KpiCard
          rotulo="Não entregues"
          valor={entregas.nao_entregues}
          contexto={entregas.nao_entregues > 0 ? "exigem reagendamento" : "nenhuma"}
          icone={PackageX}
          tom={entregas.nao_entregues > 0 ? "perigo" : "neutro"}
        />
      </div>

      <div className="painel-grade">
        <Card
          titulo="Operação de hoje"
          descricao={
            ativas.length > 0
              ? `${ativas.length} rota(s) em andamento`
              : "Nenhuma rota em andamento"
          }
          semPadding
        >
          <MapPanel
            tema={tema}
            altura={440}
            sobreposicao={
              !semOperacao && (
                <>
                  <div className="mapa-resumo mapa-resumo--marca">
                    <span className="mapa-resumo__valor numero">{rotas.em_andamento}</span>
                    <span className="mapa-resumo__rotulo">rotas ativas</span>
                  </div>
                  <div className="mapa-resumo">
                    <span className="mapa-resumo__valor numero">{entregas.total}</span>
                    <span className="mapa-resumo__rotulo">entregas</span>
                  </div>
                  <div className="mapa-resumo">
                    <span className="mapa-resumo__valor numero">
                      {rotas.motoristas_em_operacao}
                    </span>
                    <span className="mapa-resumo__rotulo">motoristas</span>
                  </div>
                </>
              )
            }
            rodape={
              semOperacao && (
                <div className="mapa-nota">
                  Nenhuma entrega cadastrada para hoje. Cadastre as entregas e
                  monte o planejamento para a operação aparecer aqui.
                </div>
              )
            }
          >
            {dados.bases.map((b) => (
              <MarcadorBase base={b} key={`b-${b.id}`} />
            ))}

            {/* Com rotas ativas o mapa mostra a execução; sem elas, mostra
                onde as entregas do dia estão. */}
            {ativas.length === 0 && (
              <MarcadoresEntregas entregas={dados.entregas_no_mapa} />
            )}

            {ativas.map((rota, i) => (
              <TrajetoRota
                key={`t-${rota.id}`}
                rota={rota}
                cor={corDaRota(i)}
                destacada={rotaSelecionada === null || rotaSelecionada === rota.id}
                aoClicar={() => setRotaSelecionada(rota.id)}
              />
            ))}

            {ativas.map((rota, i) => (
              <ParadasDaRota
                key={`p-${rota.id}`}
                rota={rota}
                cor={corDaRota(i)}
                destacada={rotaSelecionada === null || rotaSelecionada === rota.id}
              />
            ))}

            <AjustarLimites pontos={pontosMapa} ativo={pontosMapa.length > 0} />
          </MapPanel>
        </Card>

        <div className="pilha">
          <Card titulo="Rotas do dia">
            {rotas.total === 0 ? (
              <EmptyState icone={RouteIcon} titulo="Nenhuma rota planejada" compacto>
                <p>
                  Monte o planejamento para transformar as entregas pendentes em
                  rotas.
                </p>
                <Link to="/admin/planejamento">
                  <Button variante="secundario" tamanho="sm">
                    Ir ao planejamento
                  </Button>
                </Link>
              </EmptyState>
            ) : (
              <>
                <div className="mini-kpis">
                  <div>
                    <span className="mini-kpi__valor numero">{rotas.planejadas}</span>
                    <span className="mini-kpi__rotulo">planejadas</span>
                  </div>
                  <div>
                    <span className="mini-kpi__valor numero">{rotas.em_andamento}</span>
                    <span className="mini-kpi__rotulo">em andamento</span>
                  </div>
                  <div>
                    <span className="mini-kpi__valor numero">{rotas.finalizadas}</span>
                    <span className="mini-kpi__rotulo">finalizadas</span>
                  </div>
                </div>

                <div className="totais">
                  <span>
                    <RouteIcon size={13} strokeWidth={2} aria-hidden="true" />
                    {distancia(rotas.distancia_planejada_m)} planejados
                  </span>
                  <span>
                    <CircleDashed size={13} strokeWidth={2} aria-hidden="true" />
                    {duracao(rotas.duracao_estimada_s)} estimados
                  </span>
                </div>
              </>
            )}
          </Card>

          <Card titulo="Em andamento">
            {ativas.length === 0 ? (
              <EmptyState icone={Users} titulo="Ninguém na rua" compacto>
                <p>As rotas aparecem aqui quando um motorista inicia o trajeto.</p>
              </EmptyState>
            ) : (
              <ul className="rotas-ativas">
                {ativas.map((rota, i) => {
                  const total = rota.stops.reduce(
                    (s, p) => s + (p.items?.length ?? 0),
                    0,
                  );
                  const feitas = rota.stops.reduce(
                    (s, p) =>
                      s +
                      (p.items ?? []).filter((it) =>
                        ["ENTREGUE", "NAO_ENTREGUE", "CANCELADA"].includes(it.status),
                      ).length,
                    0,
                  );

                  return (
                    <li
                      key={rota.id}
                      className={`rota-ativa ${rotaSelecionada === rota.id ? "rota-ativa--sel" : ""}`}
                      onClick={() =>
                        setRotaSelecionada(rotaSelecionada === rota.id ? null : rota.id)
                      }
                    >
                      <span
                        className="rota-ativa__cor"
                        style={{ background: corDaRota(i) }}
                        aria-hidden="true"
                      />
                      <div className="rota-ativa__info">
                        <span className="rota-ativa__nome">
                          {rota.driver?.name ?? "Sem motorista"}
                        </span>
                        <span className="rota-ativa__detalhe">
                          {rota.vehicle?.name} · saiu às {hora(rota.started_at)}
                        </span>
                        <div className="progresso">
                          <div
                            className="progresso__barra"
                            style={{
                              width: `${total ? (feitas / total) * 100 : 0}%`,
                              background: corDaRota(i),
                            }}
                          />
                        </div>
                      </div>
                      <Badge tom="atencao">
                        {feitas}/{total}
                      </Badge>
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
