import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Route as RouteIcon } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { planejamento as api } from "../../api/operacao";
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
  PageHeader,
  SkeletonList,
  StatusBadge,
} from "../../components/ui";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useTheme } from "../../hooks/useTheme";
import { dataCurta, distancia, duracao, hoje, peso } from "../../utils/formato";
import "./admin.css";

/**
 * Rotas do dia.
 *
 * Mostra os planejamentos confirmados e o que aconteceu com cada rota. Um
 * planejamento descartado continua listado de propósito: saber que um
 * cenário foi calculado e jogado fora faz parte de entender o dia.
 */
/** Quantas vezes o caminhão sai da base: uma, mais uma por recarga. */
function viagensDaRota(rota) {
  return 1 + rota.stops.filter((p) => p.stop_type === "BASE_RECARGA").length;
}

export function Routes() {
  useDocumentTitle("Rotas");
  const { tema } = useTheme();

  const [data, setData] = useState(hoje());
  const [planos, setPlanos] = useState(null);
  const [plano, setPlano] = useState(null);
  const [erro, setErro] = useState("");
  const [rotaSelecionada, setRotaSelecionada] = useState(null);

  const carregar = useCallback(async () => {
    setErro("");
    setPlano(null);
    try {
      const lista = await api.listar({ data });
      setPlanos(lista);
      const confirmado = lista.find((p) => p.status === "CONFIRMADO");
      if (confirmado) setPlano(await api.obter(confirmado.id));
    } catch (e) {
      console.error("Falha ao carregar rotas", e);
      setErro(mensagemDeErro(e, "Não foi possível carregar as rotas."));
    }
  }, [data]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function abrir(resumo) {
    try {
      setPlano(await api.obter(resumo.id));
      setRotaSelecionada(null);
    } catch (e) {
      console.error("Falha ao abrir planejamento", e);
      setErro(mensagemDeErro(e));
    }
  }

  const pontos = plano
    ? plano.routes
        .flatMap((r) => r.stops ?? [])
        .filter((p) => p.latitude != null)
        .map((p) => [Number(p.latitude), Number(p.longitude)])
    : [];

  return (
    <>
      <PageHeader
        titulo="Rotas"
        descricao="O que foi planejado e o que aconteceu."
        acoes={
          <div style={{ width: 180 }}>
            <InputField
              label=""
              type="date"
              value={data}
              onChange={(e) => setData(e.target.value)}
            />
          </div>
        }
      />

      {erro && (
        <Card>
          <ErrorState mensagem={erro} aoTentarNovamente={carregar} compacto />
        </Card>
      )}

      {!planos && !erro && (
        <Card semPadding>
          <SkeletonList itens={3} />
        </Card>
      )}

      {planos?.length === 0 && (
        <Card>
          <EmptyState icone={RouteIcon} titulo="Nenhum planejamento nesta data">
            <p>Monte o planejamento para transformar as entregas em rotas.</p>
            <Link to="/admin/planejamento">
              <Button variante="secundario">Ir ao planejamento</Button>
            </Link>
          </EmptyState>
        </Card>
      )}

      {planos?.length > 0 && (
        <div className="painel-grade">
          <div className="pilha">
            <Card titulo="Planejamentos" descricao={dataCurta(data)}>
              <ul className="rotas-plano">
                {planos.map((p) => (
                  <li
                    key={p.id}
                    className={`rota-plano ${plano?.id === p.id ? "rota-plano--ativa" : ""}`}
                    onClick={() => abrir(p)}
                  >
                    <div className="rota-plano__info">
                      <span className="rota-plano__veiculo">
                        Planejamento #{p.id}
                        <Badge
                          tom={
                            p.status === "CONFIRMADO"
                              ? "sucesso"
                              : p.status === "RASCUNHO"
                                ? "atencao"
                                : "neutro"
                          }
                        >
                          {p.status.toLowerCase()}
                        </Badge>
                      </span>
                      <span className="rota-plano__numeros">
                        {distancia(p.total_distance_m)} · {duracao(p.total_duration_s)}
                        {p.matrix_source === "HAVERSINE" ? " · estimado" : ""}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>

            {plano && (
              <Card titulo="Rotas" descricao={`${plano.routes.length} rota(s)`}>
                {plano.distancias_estimadas && (
                  <Alert tom="atencao" titulo="Distâncias estimadas">
                    Este planejamento foi calculado sem o serviço de rotas: os
                    números <strong>não são distância de estrada</strong>.
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
                          {rota.driver?.name ?? "Sem motorista"}
                          <span className="placa">{rota.vehicle?.plate}</span>
                        </span>
                        <span className="rota-plano__numeros">
                          {rota.stops.filter((p) => p.stop_type === "ENTREGA").length}{" "}
                          paradas · {distancia(rota.total_distance_m)}
                          {rota.planned_weight_kg ? ` · ${peso(rota.planned_weight_kg)}` : ""}
                          {viagensDaRota(rota) > 1 ? ` · ${viagensDaRota(rota)} viagens` : ""}
                        </span>
                      </div>
                      <StatusBadge tipo="rota" valor={rota.status} />
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </div>

          <Card semPadding>
            <MapPanel tema={tema} altura={520}>
              {plano?.routes[0]?.stops?.[0]?.latitude && (
                <MarcadorBase
                  base={{
                    rotulo: "Base",
                    latitude: Number(plano.routes[0].stops[0].latitude),
                    longitude: Number(plano.routes[0].stops[0].longitude),
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

              <AjustarLimites pontos={pontos} ativo={pontos.length > 0} />
            </MapPanel>
          </Card>
        </div>
      )}
    </>
  );
}
