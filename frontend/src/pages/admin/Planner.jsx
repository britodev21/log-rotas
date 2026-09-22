import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Check, MapPinOff, Route, Sparkles, TrafficCone, Trash2, Truck } from "lucide-react";

import { bases as apiBases, motoristas as apiMotoristas, veiculos as apiVeiculos } from "../../api/cadastros";
import { mensagemDeErro } from "../../api/client";
import { entregas as apiEntregas, planejamento as apiPlano } from "../../api/operacao";
import {
  AjustarLimites,
  MapPanel,
  MarcadorBase,
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
  InputField,
  Modal,
  PageHeader,
  ProcessSteps,
  SelectField,
  SkeletonList,
} from "../../components/ui";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useTheme } from "../../hooks/useTheme";
import { useToast } from "../../hooks/useToast";
import { dataHora, distancia, duracao, hoje, peso } from "../../utils/formato";
import "./admin.css";

/**
 * Planejador de rotas.
 *
 * Três momentos distintos, e a separação entre eles é o ponto da tela:
 * SELEÇÃO (o que vai entrar), CÁLCULO (o sistema trabalha) e REVISÃO (o
 * administrador decide). Nada acontece na operação até ele confirmar.
 */

export function Planner() {
  useDocumentTitle("Planejamento");
  const toast = useToast();
  const { tema } = useTheme();

  const [data, setData] = useState(hoje());
  const [bases, setBases] = useState([]);
  const [veiculos, setVeiculos] = useState([]);
  const [motoristas, setMotoristas] = useState([]);
  const [pendentes, setPendentes] = useState([]);

  const [baseId, setBaseId] = useState("");
  const [veiculosSel, setVeiculosSel] = useState(new Set());
  const [motoristasSel, setMotoristasSel] = useState(new Set());
  const [entregasSel, setEntregasSel] = useState(new Set());
  const [inicioTurno, setInicioTurno] = useState("08:00");
  const [opcoes, setOpcoes] = useState(null);
  const [considerarTransito, setConsiderarTransito] = useState(true);

  const [carregando, setCarregando] = useState(true);
  const [erroCarga, setErroCarga] = useState("");

  const [calculando, setCalculando] = useState(false);
  const [etapa, setEtapa] = useState(0);
  const [plano, setPlano] = useState(null);
  const [erroCalculo, setErroCalculo] = useState(null);
  const [rotaSelecionada, setRotaSelecionada] = useState(null);
  const [confirmando, setConfirmando] = useState(false);
  const [atribuicoes, setAtribuicoes] = useState({});

  // --- carga inicial ------------------------------------------------------
  const carregarCadastros = useCallback(async () => {
    setCarregando(true);
    setErroCarga("");
    try {
      const [b, v, m, o] = await Promise.all([
        apiBases.listar({ active: true }),
        apiVeiculos.listar({ active: true }),
        apiMotoristas.listar({ active: true }),
        // Sem as opções a tela funciona: só não oferece o trânsito.
        apiPlano.opcoes().catch((e) => {
          console.error("Falha ao ler as opções do planejador", e);
          return null;
        }),
      ]);
      setOpcoes(o);
      setBases(b);
      setVeiculos(v);
      setMotoristas(m);
      setBaseId(String(b.find((x) => x.is_default)?.id ?? b[0]?.id ?? ""));
      setVeiculosSel(new Set(v.map((x) => x.id)));
      setMotoristasSel(new Set(m.map((x) => x.id)));
    } catch (e) {
      console.error("Falha ao carregar cadastros", e);
      setErroCarga(mensagemDeErro(e, "Não foi possível carregar os cadastros."));
    } finally {
      setCarregando(false);
    }
  }, []);

  // Trocar a data dispara uma carga nova antes de a anterior voltar, e a
  // resposta que chega por último não é necessariamente a da data na tela:
  // a de hoje chegando depois sobrescrevia a lista da data escolhida.
  const ultimaCarga = useRef(0);
  const carregarPendentes = useCallback(async () => {
    const carga = ++ultimaCarga.current;
    try {
      const lista = await apiEntregas.listar({ data, status: ["PENDENTE"] });
      if (carga !== ultimaCarga.current) return;
      setPendentes(lista);
      setEntregasSel(new Set(lista.filter((e) => e.latitude !== null).map((e) => e.id)));
    } catch (e) {
      console.error("Falha ao carregar entregas pendentes", e);
    }
  }, [data]);

  useEffect(() => {
    carregarCadastros();
  }, [carregarCadastros]);

  useEffect(() => {
    carregarPendentes();
    setPlano(null);
    setErroCalculo(null);
  }, [carregarPendentes]);

  // --- derivados ----------------------------------------------------------
  const semCoordenada = useMemo(
    () => pendentes.filter((e) => e.latitude === null),
    [pendentes],
  );

  const selecionadas = useMemo(
    () => pendentes.filter((e) => entregasSel.has(e.id)),
    [pendentes, entregasSel],
  );

  const cargaSelecionada = useMemo(
    () => selecionadas.reduce((soma, e) => soma + Number(e.weight_kg ?? 0), 0),
    [selecionadas],
  );

  const base = bases.find((b) => String(b.id) === baseId);
  const comTransito = Boolean(opcoes?.transito_disponivel && considerarTransito);
  const podeCalcular =
    baseId && veiculosSel.size > 0 && selecionadas.length > 0 && !calculando;

  function alternar(conjunto, setter, id) {
    const proximo = new Set(conjunto);
    if (proximo.has(id)) proximo.delete(id);
    else proximo.add(id);
    setter(proximo);
  }

  // --- cálculo ------------------------------------------------------------
  async function calcular() {
    setErroCalculo(null);
    setPlano(null);
    setCalculando(true);

    // Etapa 1 é verificada AQUI, no navegador, e por isso o seu resultado é
    // real: o cliente já sabe quais entregas não têm coordenada antes de
    // gastar uma viagem até o servidor.
    setEtapa(0);
    const invalidas = selecionadas.filter((e) => e.latitude === null);
    if (invalidas.length > 0) {
      setCalculando(false);
      setErroCalculo({
        mensagem: `${invalidas.length} das entregas selecionadas ainda não têm coordenada.`,
        detalhes: invalidas.map((e) => e.address ?? `Entrega ${e.id}`),
      });
      return;
    }

    setEtapa(1);
    try {
      const resultado = await apiPlano.calcular({
        date: data,
        base_id: Number(baseId),
        delivery_ids: [...entregasSel],
        vehicle_ids: [...veiculosSel],
        driver_ids: [...motoristasSel],
        inicio_turno: inicioTurno,
        limite_tempo_s: 15,
        considerar_transito: comTransito,
      });
      setEtapa(2);
      setPlano(resultado);
      setRotaSelecionada(null);
      setAtribuicoes(
        Object.fromEntries(
          resultado.routes.map((r, i) => [
            r.id,
            r.driver_id ?? [...motoristasSel][i] ?? "",
          ]),
        ),
      );
      toast.sucesso(
        "Rotas calculadas",
        `${resultado.routes.length} rota(s). Revise antes de confirmar.`,
      );
    } catch (e) {
      console.error("Falha ao calcular rotas", e);
      const dados = e?.response?.data;
      setErroCalculo({
        mensagem: mensagemDeErro(e, "Não foi possível calcular as rotas."),
        detalhes:
          dados?.detalhes?.entregas?.map(
            (x) => x.endereco ?? `Entrega ${x.id}`,
          ) ?? [],
      });
    } finally {
      setCalculando(false);
    }
  }

  async function confirmar() {
    setConfirmando(true);
    try {
      const mapa = Object.fromEntries(
        Object.entries(atribuicoes)
          .filter(([, v]) => v)
          .map(([k, v]) => [k, Number(v)]),
      );
      await apiPlano.confirmar(plano.id, mapa);
      toast.sucesso(
        "Planejamento confirmado",
        "As rotas já estão disponíveis para os motoristas.",
      );
      setPlano(null);
      await carregarPendentes();
    } catch (e) {
      console.error("Falha ao confirmar planejamento", e);
      toast.erro("Não foi possível confirmar", mensagemDeErro(e));
    } finally {
      setConfirmando(false);
    }
  }

  async function descartar() {
    try {
      await apiPlano.descartar(plano.id);
      toast.info("Planejamento descartado", "Nenhuma entrega foi alterada.");
      setPlano(null);
    } catch (e) {
      console.error("Falha ao descartar planejamento", e);
      toast.erro("Não foi possível descartar", mensagemDeErro(e));
    }
  }

  // --- mapa ---------------------------------------------------------------
  const pontosMapa = useMemo(() => {
    const pontos = [];
    if (base?.latitude) pontos.push([Number(base.latitude), Number(base.longitude)]);
    const fonte = plano ? plano.routes.flatMap((r) => r.stops ?? []) : selecionadas;
    fonte.forEach((p) => {
      if (p.latitude != null) pontos.push([Number(p.latitude), Number(p.longitude)]);
    });
    return pontos;
  }, [base, plano, selecionadas]);

  if (carregando) {
    return (
      <>
        <PageHeader titulo="Planejamento" />
        <Card>
          <SkeletonList itens={4} />
        </Card>
      </>
    );
  }

  if (erroCarga) {
    return (
      <>
        <PageHeader titulo="Planejamento" />
        <Card>
          <ErrorState mensagem={erroCarga} aoTentarNovamente={carregarCadastros} />
        </Card>
      </>
    );
  }

  if (bases.length === 0 || veiculos.length === 0) {
    return (
      <>
        <PageHeader titulo="Planejamento" />
        <Card>
          <EmptyState icone={Truck} titulo="Faltam cadastros para planejar">
            <p>
              O planejamento precisa de pelo menos uma <strong>base</strong> e um{" "}
              <strong>veículo</strong> ativos. Cadastre-os antes de montar as
              rotas do dia.
            </p>
          </EmptyState>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        titulo="Planejamento"
        descricao="Escolha o que sai hoje, calcule, revise no mapa e confirme. Nada muda na operação até a confirmação."
      />

      <div className="planejador">
        {/* ---------------------------------------------------- seleção */}
        <div className="planejador__coluna">
          <Card titulo="1. O que vai sair">
            <div className="pilha">
              <div className="form-grade">
                <InputField
                  label="Data"
                  type="date"
                  value={data}
                  onChange={(e) => setData(e.target.value)}
                  disabled={Boolean(plano)}
                />
                <SelectField
                  label="Base"
                  value={baseId}
                  onChange={(e) => setBaseId(e.target.value)}
                  disabled={Boolean(plano)}
                >
                  {bases.map((b) => (
                    <option value={String(b.id)} key={b.id}>
                      {b.name}
                      {b.is_default ? " (padrão)" : ""}
                    </option>
                  ))}
                </SelectField>
                <InputField
                  label="Início do turno"
                  type="time"
                  value={inicioTurno}
                  onChange={(e) => setInicioTurno(e.target.value)}
                  disabled={Boolean(plano)}
                />
              </div>

              {opcoes?.transito_disponivel ? (
                <label className="item-selecao opcao-transito">
                  <input
                    type="checkbox"
                    checked={considerarTransito}
                    onChange={(e) => setConsiderarTransito(e.target.checked)}
                    disabled={Boolean(plano)}
                  />
                  <span className="item-selecao__texto">
                    <span className="item-selecao__nome">Considerar o trânsito</span>
                    <span className="item-selecao__detalhe">
                      Tempo de cada trecho previsto pelo Google para este dia, a partir da
                      hora do turno. Sem isso, os tempos são de rua vazia e saem otimistas.
                    </span>
                  </span>
                  <TrafficCone size={16} strokeWidth={2} aria-hidden="true" />
                </label>
              ) : (
                opcoes && (
                  <p className="texto-3 opcao-transito__ausente">
                    Trânsito não configurado neste servidor: os tempos de deslocamento são
                    de rua vazia.
                  </p>
                )
              )}

              {semCoordenada.length > 0 && (
                <Alert
                  tom="atencao"
                  titulo={`${semCoordenada.length} entrega(s) sem coordenada`}
                >
                  Elas não podem entrar no cálculo e ficam de fora da seleção.
                  Resolva os endereços em <strong>Endereços</strong>.
                </Alert>
              )}

              <div className="selecao">
                <div className="selecao__topo">
                  <span className="rotulo-secao">
                    Entregas pendentes ({pendentes.length})
                  </span>
                  <Button
                    variante="texto"
                    tamanho="sm"
                    onClick={() =>
                      setEntregasSel(
                        entregasSel.size === pendentes.length - semCoordenada.length
                          ? new Set()
                          : new Set(
                              pendentes
                                .filter((e) => e.latitude !== null)
                                .map((e) => e.id),
                            ),
                      )
                    }
                    disabled={Boolean(plano)}
                  >
                    {entregasSel.size > 0 ? "Limpar" : "Selecionar todas"}
                  </Button>
                </div>

                {pendentes.length === 0 ? (
                  <p className="texto-3">Nenhuma entrega pendente nesta data.</p>
                ) : (
                  <ul className="selecao__lista">
                    {pendentes.map((e) => {
                      const invalida = e.latitude === null;
                      return (
                        <li key={e.id}>
                          <label
                            className={`item-selecao ${invalida ? "item-selecao--bloqueada" : ""}`}
                          >
                            <input
                              type="checkbox"
                              checked={entregasSel.has(e.id)}
                              onChange={() => alternar(entregasSel, setEntregasSel, e.id)}
                              disabled={invalida || Boolean(plano)}
                            />
                            <span className="item-selecao__texto">
                              <span className="item-selecao__nome">
                                {e.recipient_name || e.customer?.name || `Entrega ${e.id}`}
                              </span>
                              <span className="item-selecao__detalhe">
                                {e.address ?? "sem endereço"}
                              </span>
                            </span>
                            {invalida ? (
                              <Badge tom="atencao" ponto>
                                sem pino
                              </Badge>
                            ) : (
                              e.weight_kg && (
                                <span className="item-selecao__peso numero">
                                  {peso(e.weight_kg)}
                                </span>
                              )
                            )}
                          </label>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </div>
          </Card>

          <Card titulo="2. Com o que">
            <div className="pilha">
              <div>
                <p className="rotulo-secao">Veículos</p>
                <ul className="selecao__lista selecao__lista--curta">
                  {veiculos.map((v) => (
                    <li key={v.id}>
                      <label className="item-selecao">
                        <input
                          type="checkbox"
                          checked={veiculosSel.has(v.id)}
                          onChange={() => alternar(veiculosSel, setVeiculosSel, v.id)}
                          disabled={Boolean(plano)}
                        />
                        <span className="item-selecao__texto">
                          <span className="item-selecao__nome">{v.name}</span>
                          <span className="item-selecao__detalhe">
                            {v.plate}
                            {v.capacity_weight_kg
                              ? ` · ${peso(v.capacity_weight_kg)}`
                              : " · sem limite informado"}
                          </span>
                        </span>
                        {v.crew_size > 1 && <Badge tom="info">{v.crew_size} pessoas</Badge>}
                      </label>
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <p className="rotulo-secao">Motoristas</p>
                {motoristas.length === 0 ? (
                  <Alert tom="atencao">
                    Nenhum motorista ativo. Você pode calcular, mas não vai
                    conseguir confirmar sem atribuir alguém a cada rota.
                  </Alert>
                ) : (
                  <ul className="selecao__lista selecao__lista--curta">
                    {motoristas.map((m) => (
                      <li key={m.id}>
                        <label className="item-selecao">
                          <input
                            type="checkbox"
                            checked={motoristasSel.has(m.id)}
                            onChange={() =>
                              alternar(motoristasSel, setMotoristasSel, m.id)
                            }
                            disabled={Boolean(plano)}
                          />
                          <span className="item-selecao__texto">
                            <span className="item-selecao__nome">{m.name}</span>
                          </span>
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </Card>
        </div>

        {/* ------------------------------------------------ mapa e resumo */}
        <div className="planejador__coluna planejador__coluna--larga">
          <Card semPadding>
            <MapPanel
              tema={tema}
              altura={440}
              sobreposicao={
                plano && (
                  <>
                    <div className="mapa-resumo">
                      <span className="mapa-resumo__valor numero">
                        {plano.routes.length}
                      </span>
                      <span className="mapa-resumo__rotulo">rotas</span>
                    </div>
                    <div className="mapa-resumo">
                      <span className="mapa-resumo__valor numero">
                        {distancia(plano.total_distance_m)}
                      </span>
                      <span className="mapa-resumo__rotulo">distância</span>
                    </div>
                    <div className="mapa-resumo">
                      <span className="mapa-resumo__valor numero">
                        {duracao(plano.total_duration_s)}
                      </span>
                      <span className="mapa-resumo__rotulo">duração</span>
                    </div>
                  </>
                )
              }
            >
              {base?.latitude && (
                <MarcadorBase
                  base={{
                    rotulo: base.name,
                    latitude: Number(base.latitude),
                    longitude: Number(base.longitude),
                  }}
                />
              )}

              {plano?.routes.map((rota, i) => (
                <TrajetoRota
                  key={`t-${rota.id}`}
                  rota={rota}
                  cor={corDaRota(i)}
                  destacada={rotaSelecionada === null || rotaSelecionada === rota.id}
                  aoClicar={() => setRotaSelecionada(rota.id)}
                />
              ))}

              {plano?.routes.map((rota, i) => (
                <ParadasDaRota
                  key={`p-${rota.id}`}
                  rota={rota}
                  cor={corDaRota(i)}
                  destacada={rotaSelecionada === null || rotaSelecionada === rota.id}
                />
              ))}

              <AjustarLimites pontos={pontosMapa} />
            </MapPanel>
          </Card>

          {calculando && (
            <Card titulo="Calculando">
              <ProcessSteps
                etapas={[
                  {
                    id: "enderecos",
                    nome: "Conferindo endereços",
                    estado: etapa > 0 ? "concluido" : "executando",
                  },
                  {
                    id: "servidor",
                    nome: comTransito
                      ? "Agrupando paradas, medindo o trânsito e otimizando"
                      : "Agrupando paradas, medindo distâncias e otimizando",
                    detalhe: "Executado no servidor, em sequência",
                    estado: etapa > 1 ? "concluido" : etapa === 1 ? "executando" : "aguardando",
                  },
                  {
                    id: "resultado",
                    nome: "Montando o resultado",
                    estado: etapa > 1 ? "concluido" : "aguardando",
                  },
                ]}
              />
              <p className="texto-3" style={{ marginTop: "var(--e-3)" }}>
                O servidor não informa progresso dentro da etapa de cálculo, então
                ela aparece como uma só — preferimos isso a uma barra que sobe
                sem corresponder a nada.
              </p>
            </Card>
          )}

          {erroCalculo && (
            <Card>
              <ErrorState
                titulo="Não foi possível calcular"
                mensagem={erroCalculo.mensagem}
                aoTentarNovamente={calcular}
                compacto
              />
              {erroCalculo.detalhes?.length > 0 && (
                <ul className="lista-erro">
                  {erroCalculo.detalhes.map((d) => (
                    <li key={d}>
                      <MapPinOff size={13} strokeWidth={2} aria-hidden="true" />
                      {d}
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          )}

          {!plano && !calculando && (
            <Card>
              <div className="resumo-calculo">
                <div className="resumo-calculo__numeros">
                  <div>
                    <span className="resumo-calculo__valor numero">
                      {selecionadas.length}
                    </span>
                    <span className="resumo-calculo__rotulo">entregas</span>
                  </div>
                  <div>
                    <span className="resumo-calculo__valor numero">
                      {veiculosSel.size}
                    </span>
                    <span className="resumo-calculo__rotulo">veículos</span>
                  </div>
                  <div>
                    <span className="resumo-calculo__valor numero">
                      {motoristasSel.size}
                    </span>
                    <span className="resumo-calculo__rotulo">motoristas</span>
                  </div>
                  <div>
                    <span className="resumo-calculo__valor numero">
                      {cargaSelecionada > 0 ? peso(cargaSelecionada) : "—"}
                    </span>
                    <span className="resumo-calculo__rotulo">carga</span>
                  </div>
                </div>

                <Button
                  icone={Sparkles}
                  tamanho="lg"
                  larguraTotal
                  onClick={calcular}
                  disabled={!podeCalcular}
                >
                  Calcular rotas
                </Button>
              </div>
            </Card>
          )}

          {plano && (
            <ResultadoPlano
              plano={plano}
              motoristas={motoristas}
              atribuicoes={atribuicoes}
              setAtribuicoes={setAtribuicoes}
              rotaSelecionada={rotaSelecionada}
              setRotaSelecionada={setRotaSelecionada}
              onConfirmar={confirmar}
              onDescartar={descartar}
              confirmando={confirmando}
            />
          )}
        </div>
      </div>
    </>
  );
}

/** Por que o trânsito ficou de fora, quando ficou por escolha ou configuração.
 *  Falha do Google chega como aviso do servidor, com a causa. */
const SEM_TRANSITO = {
  "desligado neste calculo": "o trânsito foi desligado neste cálculo",
  "transito nao configurado": "o servidor não tem trânsito configurado",
};

/**
 * Quanto o trânsito pesou no plano — em tempo, não em fator: "38 min a
 * mais" diz alguma coisa a quem monta o dia; "fator 1,75" não.
 */
function ResumoTransito({ transito }) {
  // Planos calculados antes de o trânsito existir não têm o campo.
  if (!transito) return null;

  if (!transito.considerado) {
    const motivo = SEM_TRANSITO[transito.motivo];
    if (!motivo) return null;
    return (
      <p className="transito-resumo transito-resumo--livre">
        <TrafficCone size={16} strokeWidth={2} aria-hidden="true" />
        <span>
          Tempos de rua vazia: {motivo}. Os horários tendem a ser otimistas.
        </span>
      </p>
    );
  }

  const livre = transito.estrada_livre_s ?? 0;
  const comTransito = transito.estrada_transito_s ?? 0;
  const extra = comTransito - livre;
  const pct = livre > 0 ? Math.round((extra / livre) * 100) : null;
  const origem = [
    `${transito.consultas} consulta(s) ao Google`,
    transito.pares_do_cache > 0 && `${transito.pares_do_cache} trechos reaproveitados`,
    transito.pares_por_fator > 0 && `${transito.pares_por_fator} estimados pelo fator`,
  ].filter(Boolean);
  // O Google não prevê o passado: com o turno já começado, vale o de agora.
  const turnoJaComecou =
    transito.partida_do_turno &&
    new Date(transito.partida) - new Date(transito.partida_do_turno) > 60_000;

  return (
    <div className="transito-resumo">
      <TrafficCone size={16} strokeWidth={2} aria-hidden="true" />
      <div className="transito-resumo__texto">
        <strong>
          {turnoJaComecou
            ? `Com o trânsito de agora (${dataHora(transito.partida)}) — o turno já tinha começado`
            : `Com o trânsito previsto para ${dataHora(transito.partida)}`}
        </strong>
        <span>
          {duracao(comTransito)} de deslocamento
          {extra > 0 && (
            <>
              {" "}— {duracao(extra)} a mais que com a rua vazia
              {pct !== null && ` (+${pct}%)`}
            </>
          )}
          .
        </span>
        <span className="texto-3">{origem.join(" · ")}</span>
      </div>
    </div>
  );
}

function ResultadoPlano({
  plano,
  motoristas,
  atribuicoes,
  setAtribuicoes,
  rotaSelecionada,
  setRotaSelecionada,
  onConfirmar,
  onDescartar,
  confirmando,
}) {
  const [confirmacaoAberta, setConfirmacaoAberta] = useState(false);
  const semMotorista = plano.routes.filter((r) => !atribuicoes[r.id]).length;

  return (
    <>
      <Card
        titulo="3. Revise antes de confirmar"
        descricao="Enquanto você não confirmar, nada muda na operação."
        acoes={<Badge tom="atencao">rascunho</Badge>}
      >
        {plano.distancias_estimadas && (
          <Alert tom="atencao" titulo="Distâncias estimadas em linha reta">
            O serviço de rotas não respondeu, então os números abaixo{" "}
            <strong>não são distância de estrada</strong>. A ordem das paradas
            continua válida, mas quilometragem e duração são aproximadas.
          </Alert>
        )}

        <ResumoTransito transito={plano.transito} />

        {plano.avisos?.map((aviso) => (
          <Alert tom="info" key={aviso}>
            {aviso}
          </Alert>
        ))}

        {plano.unassigned?.length > 0 && (
          <Alert
            tom="atencao"
            titulo={`${plano.unassigned.length} parada(s) ficaram de fora`}
          >
            <ul className="lista-erro">
              {plano.unassigned.map((u, i) => (
                <li key={i}>
                  {u.rotulo} — {u.motivo}
                </li>
              ))}
            </ul>
            Essas entregas continuam pendentes e voltam no próximo planejamento.
          </Alert>
        )}

        <ul className="rotas-plano">
          {plano.routes.map((rota, i) => (
            <li
              key={rota.id}
              className={`rota-plano ${rotaSelecionada === rota.id ? "rota-plano--ativa" : ""}`}
              onClick={() =>
                setRotaSelecionada(rotaSelecionada === rota.id ? null : rota.id)
              }
            >
              <span
                className="rota-plano__cor"
                style={{ background: corDaRota(i) }}
                aria-hidden="true"
              />

              <div className="rota-plano__info">
                <span className="rota-plano__veiculo">
                  {rota.vehicle?.name}
                  <span className="placa">{rota.vehicle?.plate}</span>
                </span>
                <span className="rota-plano__numeros">
                  {rota.stops.filter((p) => p.stop_type === "ENTREGA").length} paradas ·{" "}
                  {distancia(rota.total_distance_m)} · {duracao(rota.estimated_duration_s)}
                  {rota.planned_weight_kg ? ` · ${peso(rota.planned_weight_kg)}` : ""}
                </span>
              </div>

              <div
                className="rota-plano__motorista"
                onClick={(e) => e.stopPropagation()}
              >
                <SelectField
                  label=""
                  value={atribuicoes[rota.id] ?? ""}
                  onChange={(e) =>
                    setAtribuicoes((a) => ({ ...a, [rota.id]: e.target.value }))
                  }
                >
                  <option value="">Sem motorista</option>
                  {motoristas.map((m) => (
                    <option value={String(m.id)} key={m.id}>
                      {m.name}
                    </option>
                  ))}
                </SelectField>
              </div>
            </li>
          ))}
        </ul>

        {rotaSelecionada && (
          <ol className="sequencia">
            {plano.routes
              .find((r) => r.id === rotaSelecionada)
              ?.stops.map((parada) => (
                <li className="sequencia__item" key={parada.id}>
                  <span className="sequencia__ordem numero">
                    {parada.stop_type === "ENTREGA" ? parada.sequence : "—"}
                  </span>
                  <span className="sequencia__texto">
                    <strong>{parada.label}</strong>
                    {parada.address && (
                      <span className="sequencia__endereco">{parada.address}</span>
                    )}
                  </span>
                  {parada.items?.length > 1 && (
                    <Badge tom="info">{parada.items.length} entregas</Badge>
                  )}
                </li>
              ))}
          </ol>
        )}

        <div className="acoes-direita" style={{ marginTop: "var(--e-5)" }}>
          <Button variante="secundario" icone={Trash2} onClick={onDescartar}>
            Descartar
          </Button>
          <Button
            icone={Check}
            onClick={() => setConfirmacaoAberta(true)}
            disabled={semMotorista > 0}
            title={
              semMotorista > 0
                ? "Atribua um motorista a cada rota antes de confirmar."
                : undefined
            }
          >
            Confirmar planejamento
          </Button>
        </div>

        {semMotorista > 0 && (
          <p className="texto-3" style={{ marginTop: "var(--e-2)", textAlign: "right" }}>
            {semMotorista} rota(s) ainda sem motorista.
          </p>
        )}
      </Card>

      <Modal
        aberto={confirmacaoAberta}
        titulo="Confirmar planejamento"
        descricao="Esta ação coloca as rotas em operação."
        onFechar={() => setConfirmacaoAberta(false)}
        tamanho="sm"
      >
        <div className="pilha">
          <p>
            {plano.routes.length} rota(s) passarão a <strong>planejada</strong> e
            ficarão visíveis para os motoristas. As entregas saem de pendente.
          </p>
          <Alert tom="atencao">
            Um planejamento confirmado não volta atrás. Para desfazer, será
            preciso cancelar as rotas — que podem já ter começado.
          </Alert>

          <div className="acoes-direita">
            <Button variante="secundario" onClick={() => setConfirmacaoAberta(false)}>
              Voltar
            </Button>
            <Button
              icone={Route}
              carregando={confirmando}
              onClick={async () => {
                await onConfirmar();
                setConfirmacaoAberta(false);
              }}
            >
              Confirmar
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}
