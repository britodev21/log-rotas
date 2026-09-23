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
  CaminhoesAoVivo,
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

/** Posição dos caminhões. Ritmo próprio, mais curto que o dos indicadores:
 *  o caminhão muda a cada poucos segundos, o resto do painel não. */
const INTERVALO_AO_VIVO_MS = 5000;

const SITUACAO = {
  EM_MOVIMENTO: { texto: "em movimento", tom: "sucesso" },
  PARADO: { texto: "parado", tom: "atencao" },
  NA_PARADA: { texto: "na entrega", tom: "info" },
  SEM_SINAL: { texto: "sem sinal", tom: "perigo" },
  SEM_POSICAO: { texto: "aguardando GPS", tom: "neutro" },
};

const FONTE = {
  "OSRM+TRANSITO": "com trânsito",
  OSRM: "rua livre",
  HAVERSINE: "estimativa",
  PLANEJADO: "horário do plano",
};

/** "+12 min", "no horário", "8 min adiantado". Tolerância de 5 min: menos
 *  que isso é ruído do próprio cálculo, não atraso. */
function atrasoTexto(segundos) {
  if (segundos == null) return null;
  const minutos = Math.round(segundos / 60);
  if (Math.abs(minutos) <= 5) return { texto: "no horário", tom: "sucesso" };
  if (minutos > 0) return { texto: `+${minutos} min`, tom: minutos > 20 ? "perigo" : "atencao" };
  return { texto: `${-minutos} min adiantado`, tom: "info" };
}

/** Consulta os caminhões em rota enquanto houver algum e a aba estiver à
 *  vista. Aba escondida não precisa de caminhão andando. */
function useAoVivo(ativo) {
  const [dados, setDados] = useState(null);

  useEffect(() => {
    if (!ativo) {
      setDados(null);
      return undefined;
    }
    let vivo = true;
    const carregar = async () => {
      if (document.visibilityState === "hidden") return;
      try {
        const resposta = await api.aoVivo();
        if (vivo) setDados(resposta);
      } catch (e) {
        // Mantém a última posição conhecida; o rótulo "sem sinal" e a idade
        // da posição já dizem que ela está envelhecendo.
        console.warn("Falha ao atualizar os caminhões", e?.message);
      }
    };
    carregar();
    const id = setInterval(carregar, INTERVALO_AO_VIVO_MS);
    document.addEventListener("visibilitychange", carregar);
    return () => {
      vivo = false;
      clearInterval(id);
      document.removeEventListener("visibilitychange", carregar);
    };
  }, [ativo]);

  return dados;
}

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
  const aoVivo = useAoVivo((dados?.rotas_ativas?.length ?? 0) > 0);

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
  const corDe = (rotaId) => {
    const i = ativas.findIndex((r) => r.id === rotaId);
    return corDaRota(i >= 0 ? i : 0);
  };
  const vivoDe = (rotaId) => aoVivo?.rotas.find((r) => r.rota_id === rotaId) ?? null;
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
          data-tour="painel-mapa"
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

            {aoVivo && (
              <CaminhoesAoVivo
                rotas={aoVivo.rotas}
                corDe={corDe}
                destacada={rotaSelecionada}
              />
            )}

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
                        <InfoAoVivo vivo={vivoDe(rota.id)} />
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

/**
 * O que o escritório precisa saber de um caminhão em rota: se está andando,
 * quando chega na próxima parada, se está atrasado e quando termina. E de
 * onde veio o tempo — "rua livre" e "com trânsito" não merecem a mesma
 * confiança, e a tela não pode tratá-los igual.
 */
function InfoAoVivo({ vivo }) {
  if (!vivo) return null;
  const situacao = SITUACAO[vivo.situacao] ?? SITUACAO.SEM_POSICAO;
  const proxima = vivo.proxima;
  const atraso = atrasoTexto(proxima?.atraso_s);
  const previsao = vivo.previsao;
  const idade =
    vivo.idade_s == null
      ? null
      : vivo.idade_s < 90
        ? `${vivo.idade_s} s`
        : `${Math.round(vivo.idade_s / 60)} min`;

  return (
    <div className="ao-vivo">
      <div className="ao-vivo__linha">
        <Badge tom={situacao.tom} ponto>
          {situacao.texto}
          {vivo.situacao === "SEM_SINAL" && idade ? ` há ${idade}` : ""}
        </Badge>
        {idade && vivo.situacao !== "SEM_SINAL" && (
          <span className="ao-vivo__idade">posição de {idade} atrás</span>
        )}
      </div>

      {proxima && (
        <div className="ao-vivo__linha">
          <span className="ao-vivo__proxima">
            {proxima.tipo === "BASE_RETORNO"
              ? "Volta à base"
              : proxima.tipo === "BASE_RECARGA"
                ? "Recarga na base"
                : `Próxima: ${proxima.rotulo ?? "entrega"}`}
            {proxima.chegada_prevista && (
              <>
                {" "}
                · chega <strong className="numero">{hora(proxima.chegada_prevista)}</strong>
              </>
            )}
          </span>
          {atraso && <Badge tom={atraso.tom}>{atraso.texto}</Badge>}
        </div>
      )}

      <div className="ao-vivo__linha ao-vivo__rodape">
        {previsao.termino_previsto && (
          <span>
            termina às <span className="numero">{hora(previsao.termino_previsto)}</span>
          </span>
        )}
        <span className="ao-vivo__fonte" title={previsao.aviso ?? undefined}>
          {FONTE[previsao.fonte] ?? previsao.fonte}
        </span>
      </div>
    </div>
  );
}
