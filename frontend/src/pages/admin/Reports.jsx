import { useCallback, useEffect, useMemo, useState } from "react";
import { Download, PackageCheck, Table2 } from "lucide-react";

import { motoristas as apiMotoristas } from "../../api/cadastros";
import { mensagemDeErro } from "../../api/client";
import { relatorios as api } from "../../api/relatorios";
import {
  BarrasRotuladas,
  ColunasPorDia,
  ComparacaoPlanejadoReal,
} from "../../components/charts/Graficos";
import {
  Alert,
  Button,
  Card,
  EmptyState,
  ErrorState,
  InputField,
  KpiCard,
  PageHeader,
  SelectField,
  SkeletonList,
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
} from "../../components/ui";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useToast } from "../../hooks/useToast";
import { distancia, duracao } from "../../utils/formato";
import "./admin.css";

const MOTIVOS = {
  CLIENTE_AUSENTE: "Cliente ausente",
  ENDERECO_INCORRETO: "Endereço incorreto",
  RECUSA: "Cliente recusou",
  ESTABELECIMENTO_FECHADO: "Estabelecimento fechado",
  PROBLEMA_ACESSO: "Problema de acesso",
  AVARIA: "Avaria",
  FALTA_PRODUTO: "Falta de produto",
  OUTRO: "Outro",
  NAO_INFORMADO: "Sem motivo registrado",
};

const FONTES = {
  GOOGLE_TRANSITO: "Com trânsito (Google)",
  OSRM: "Rua livre (OSRM)",
  HAVERSINE: "Linha reta (estimativa)",
  DESCONHECIDA: "Sem plano registrado",
};

/** Faixas de pontualidade, da melhor para a pior, com a cor do estado. */
const FAIXAS = [
  { chave: "no_horario", rotulo: "No horário", cor: "var(--sucesso)" },
  { chave: "adiantadas", rotulo: "Adiantadas (mais de 15 min)", cor: "var(--info)" },
  { chave: "atrasadas", rotulo: "Atrasadas até 1 h", cor: "var(--atencao)" },
  { chave: "muito_atrasadas", rotulo: "Atrasadas mais de 1 h", cor: "var(--perigo)" },
];

function hoje() {
  return new Date().toISOString().slice(0, 10);
}

function diasAtras(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

function porcento(valor) {
  return valor == null ? "—" : `${Math.round(valor * 100)}%`;
}

/** Atraso em minutos, com sinal — adiantado é informação, não erro. */
function atraso(segundos) {
  if (segundos == null) return "—";
  const minutos = Math.round(segundos / 60);
  if (minutos === 0) return "no horário";
  return minutos > 0 ? `${minutos} min de atraso` : `${-minutos} min adiantado`;
}

function diaCurto(iso, completo = false) {
  const [ano, mes, dia] = iso.split("-");
  return completo ? `${dia}/${mes}/${ano}` : `${dia}/${mes}`;
}

/**
 * Relatórios: o que foi prometido, o que aconteceu, e a diferença.
 *
 * A tela é lida de cima para baixo como a conversa que a operação tem toda
 * semana: quanto saiu, o que falhou e por quê, os horários bateram, e —
 * a parte que melhora o mês seguinte — os tempos que o sistema usa para
 * planejar correspondem ao que o caminhão leva de verdade.
 *
 * Todo bloco mostra o tamanho da amostra. Média de três entregas não
 * calibra nada, e uma tela que não diz isso convida a decidir com ela.
 */
export function Reports() {
  useDocumentTitle("Relatórios");
  const toast = useToast();

  const [de, setDe] = useState(diasAtras(29));
  const [ate, setAte] = useState(hoje());
  const [motoristaId, setMotoristaId] = useState("");
  const [motoristas, setMotoristas] = useState([]);
  const [dados, setDados] = useState(null);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [tabelaDoDia, setTabelaDoDia] = useState(false);
  const [baixando, setBaixando] = useState(false);

  useEffect(() => {
    apiMotoristas
      .listar({ active: true })
      .then(setMotoristas)
      .catch((e) => console.error("Falha ao carregar motoristas", e));
  }, []);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro("");
    try {
      setDados(await api.periodo({ de, ate, motorista_id: motoristaId || undefined }));
    } catch (e) {
      console.error("Falha ao carregar o relatório", e);
      setErro(mensagemDeErro(e, "Não foi possível carregar o relatório."));
    } finally {
      setCarregando(false);
    }
  }, [de, ate, motoristaId]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function baixarCsv() {
    setBaixando(true);
    try {
      await api.baixarCsv({ de, ate, motorista_id: motoristaId || undefined });
    } catch (e) {
      console.error("Falha ao baixar o CSV", e);
      toast.erro("Não foi possível baixar", mensagemDeErro(e));
    } finally {
      setBaixando(false);
    }
  }

  const motivos = useMemo(
    () =>
      (dados?.entregas.motivos ?? []).map((m) => ({
        rotulo: MOTIVOS[m.motivo] ?? m.motivo,
        valor: m.quantidade,
        cor: "var(--serie-2)",
      })),
    [dados],
  );

  const faixas = useMemo(() => {
    const p = dados?.pontualidade;
    if (!p?.paradas) return [];
    return FAIXAS.map((f) => ({
      rotulo: f.rotulo,
      valor: p[f.chave],
      cor: f.cor,
      detalhe: `${Math.round((p[f.chave] / p.paradas) * 100)}% das paradas`,
    }));
  }, [dados]);

  const filtros = (
    <div className="relatorio-filtros">
      <InputField label="De" type="date" value={de} onChange={(e) => setDe(e.target.value)} />
      <InputField label="Até" type="date" value={ate} onChange={(e) => setAte(e.target.value)} />
      <SelectField
        label="Motorista"
        value={motoristaId}
        onChange={(e) => setMotoristaId(e.target.value)}
      >
        <option value="">Todos</option>
        {motoristas.map((m) => (
          <option value={String(m.id)} key={m.id}>
            {m.name}
          </option>
        ))}
      </SelectField>
      <div className="relatorio-filtros__atalhos">
        <Button variante="secundario" tamanho="sm" onClick={() => { setDe(diasAtras(6)); setAte(hoje()); }}>
          7 dias
        </Button>
        <Button variante="secundario" tamanho="sm" onClick={() => { setDe(diasAtras(29)); setAte(hoje()); }}>
          30 dias
        </Button>
        <Button
          variante="secundario"
          tamanho="sm"
          icone={Download}
          carregando={baixando}
          onClick={baixarCsv}
        >
          Baixar CSV
        </Button>
      </div>
    </div>
  );

  if (erro) {
    return (
      <>
        <PageHeader titulo="Relatórios" />
        <Card>{filtros}</Card>
        <Card>
          <ErrorState mensagem={erro} aoTentarNovamente={carregar} />
        </Card>
      </>
    );
  }

  const entregas = dados?.entregas;
  const rotas = dados?.rotas;
  const pontualidade = dados?.pontualidade;
  const parada = dados?.tempo_de_parada;
  const semRegistro = dados?.paradas_sem_registro ?? 0;
  const vazio = dados && entregas.total === 0 && rotas.total === 0;

  return (
    <>
      <PageHeader
        titulo="Relatórios"
        descricao="O que foi prometido, o que aconteceu, e a diferença entre os dois."
      />

      <Card className="relatorio-card-filtros">{filtros}</Card>

      {carregando && (
        <Card>
          <SkeletonList itens={5} />
        </Card>
      )}

      {!carregando && vazio && (
        <Card>
          <EmptyState icone={PackageCheck} titulo="Nenhuma rota neste período">
            <p>
              Os números aparecem quando houver rota confirmada e executada no período
              escolhido. Experimente ampliar as datas.
            </p>
          </EmptyState>
        </Card>
      )}

      {!carregando && !vazio && (
        <>
          <div className="kpis">
            <KpiCard rotulo="Entregas realizadas" valor={entregas.entregues} />
            <KpiCard
              rotulo="Taxa de sucesso"
              valor={porcento(entregas.taxa_sucesso)}
              contexto={`${entregas.nao_entregues} não entregue(s)`}
            />
            <KpiCard
              rotulo="Rotas"
              valor={rotas.total}
              contexto={rotas.viagens > rotas.total ? `${rotas.viagens} viagens` : undefined}
            />
            <KpiCard rotulo="Distância" valor={distancia(rotas.distancia_m)} />
            <KpiCard rotulo="Tempo em rota" valor={duracao(rotas.tempo_em_rota_s)} />
          </div>

          <Card
            titulo="Entregas por dia"
            descricao="Resolvidas em cada dia do período."
            acoes={
              <Button
                variante="secundario"
                tamanho="sm"
                icone={Table2}
                onClick={() => setTabelaDoDia((v) => !v)}
              >
                {tabelaDoDia ? "Ver gráfico" : "Ver tabela"}
              </Button>
            }
          >
            {dados.por_dia.length === 0 ? (
              <p className="texto-3">Nenhuma entrega resolvida no período.</p>
            ) : tabelaDoDia ? (
              <Table>
                <THead>
                  <TH>Dia</TH>
                  <TH>Entregues</TH>
                  <TH>Não entregues</TH>
                </THead>
                <TBody>
                  {dados.por_dia.map((d) => (
                    <TR key={d.dia}>
                      <TD>{diaCurto(d.dia, true)}</TD>
                      <TD>
                        <span className="numero">{d.entregues}</span>
                      </TD>
                      <TD>
                        <span className="numero">{d.nao_entregues}</span>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            ) : (
              <ColunasPorDia
                dias={dados.por_dia}
                formatarDia={diaCurto}
                series={[
                  { chave: "entregues", rotulo: "Entregues", cor: "var(--serie-1)" },
                  { chave: "nao_entregues", rotulo: "Não entregues", cor: "var(--serie-2)" },
                ]}
              />
            )}
          </Card>

          <div className="relatorio-grade">
            <Card
              titulo="Pontualidade"
              descricao={`Chegada real contra a prevista, com tolerância de ${Math.round(
                (pontualidade.tolerancia_s ?? 900) / 60,
              )} min.`}
            >
              {pontualidade.paradas === 0 ? (
                <p className="texto-3">
                  Nenhuma parada com hora de chegada registrada no período.
                </p>
              ) : (
                <>
                  <p className="relatorio-destaque">
                    <strong className="numero">{atraso(pontualidade.atraso_mediano_s)}</strong>
                    <span>na parada típica ({pontualidade.paradas} paradas medidas)</span>
                  </p>
                  <BarrasRotuladas itens={faixas} />
                  {semRegistro > 0 && (
                    <Alert tom="atencao" titulo={`${semRegistro} parada(s) sem hora de chegada`}>
                      Elas foram concluídas sem o registro de chegada e ficam de fora desta
                      conta — os percentuais acima são sobre as {pontualidade.paradas} que têm
                      registro.
                    </Alert>
                  )}
                </>
              )}
            </Card>

            <Card titulo="Por que não foi entregue" descricao="Motivos registrados pelo motorista.">
              {motivos.length === 0 ? (
                <p className="texto-3">Nenhum insucesso no período.</p>
              ) : (
                <BarrasRotuladas itens={motivos} />
              )}
            </Card>
          </div>

          <Card
            titulo="Os tempos planejados batem com a realidade?"
            descricao="É o que melhora o planejamento do mês que vem."
          >
            <div className="relatorio-grade">
              <div>
                <h4 className="relatorio-subtitulo">Tempo parado na entrega</h4>
                {parada.amostras === 0 ? (
                  <p className="texto-3">
                    {parada.registros_em_bloco > 0
                      ? `Nas ${parada.registros_em_bloco} parada(s) do período, chegada e saída foram marcadas no mesmo minuto — isso mede o registro, não a entrega.`
                      : "Nenhuma parada com chegada e saída registradas no período."}
                  </p>
                ) : (
                  <>
                    <ComparacaoPlanejadoReal
                      planejado={parada.planejado_medio_s}
                      real={parada.real_mediano_s}
                      formatar={duracao}
                      rotulos={["Planejado", "Real (típico)"]}
                    />
                    <p className="texto-3">
                      {parada.amostras} parada(s) medida(s). Metade levou até{" "}
                      {duracao(parada.real_mediano_s)}; uma em cada dez passou de{" "}
                      {duracao(parada.real_p90_s)}.
                    </p>
                    {parada.registros_em_bloco > 0 && (
                      <p className="texto-3">
                        {parada.registros_em_bloco} parada(s) ficaram de fora: chegada e saída
                        foram marcadas no mesmo minuto, o que mede o registro, não a entrega.
                      </p>
                    )}
                    {parada.amostras < parada.amostra_minima && (
                      <Alert tom="atencao" titulo="Amostra pequena">
                        Com menos de {parada.amostra_minima} paradas, este número ainda não
                        serve para mudar o tempo padrão em Configurações.
                      </Alert>
                    )}
                  </>
                )}
              </div>

              <div>
                <h4 className="relatorio-subtitulo">Deslocamento entre paradas</h4>
                {dados.deslocamento.length === 0 ? (
                  <p className="texto-3">Sem trechos com chegada e saída registradas.</p>
                ) : (
                  <>
                    <Table>
                      <THead>
                        <TH>Fonte do tempo</TH>
                        <TH>Trechos</TH>
                        <TH>Previsto</TH>
                        <TH>Real</TH>
                      </THead>
                      <TBody>
                        {dados.deslocamento.map((d) => (
                          <TR key={d.fonte}>
                            <TD>{FONTES[d.fonte] ?? d.fonte}</TD>
                            <TD>
                              <span className="numero">{d.amostras}</span>
                            </TD>
                            <TD>
                              <span className="numero">{duracao(d.previsto_mediano_s)}</span>
                            </TD>
                            <TD>
                              <span className="numero">{duracao(d.real_mediano_s)}</span>
                              <span className="relatorio-razao">
                                {d.razao_mediana >= 1
                                  ? `${Math.round((d.razao_mediana - 1) * 100)}% a mais`
                                  : `${Math.round((1 - d.razao_mediana) * 100)}% a menos`}
                              </span>
                            </TD>
                          </TR>
                        ))}
                      </TBody>
                    </Table>
                    <p className="texto-3">
                      O real inclui o que o plano não previa — uma parada para abastecer, o
                      portão que demora. Por isso a comparação é do trecho típico, não da
                      média.
                    </p>
                  </>
                )}
              </div>
            </div>
          </Card>

          <Card titulo="Por motorista" descricao="Todos do período, mesmo com o filtro acima." semPadding>
            {dados.por_motorista.length === 0 ? (
              <p className="texto-3" style={{ padding: "var(--e-4)" }}>
                Nenhuma rota com motorista no período.
              </p>
            ) : (
              <Table>
                <THead>
                  <TH>Motorista</TH>
                  <TH>Entregas</TH>
                  <TH>Entregues</TH>
                  <TH>Não entregues</TH>
                  <TH>Taxa</TH>
                  <TH>Chegada típica</TH>
                </THead>
                <TBody>
                  {dados.por_motorista.map((m) => (
                    <TR key={m.id}>
                      <TD>{m.nome}</TD>
                      <TD>
                        <span className="numero">{m.entregas}</span>
                      </TD>
                      <TD>
                        <span className="numero">{m.entregues}</span>
                      </TD>
                      <TD>
                        <span className="numero">{m.nao_entregues}</span>
                      </TD>
                      <TD>
                        <span className="numero">{porcento(m.taxa_sucesso)}</span>
                      </TD>
                      <TD>{atraso(m.atraso_medio_s)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            )}
          </Card>
        </>
      )}
    </>
  );
}
