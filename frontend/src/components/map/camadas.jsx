import { useEffect, useMemo } from "react";
import { Marker, Polyline, Popup, useMap } from "react-leaflet";
import L from "leaflet";

import { STATUS_ENTREGA } from "../ui/Badge";
import { decodificarPolyline } from "../../utils/polyline";
import "./camadas.css";

/**
 * Camadas do mapa: marcadores e trajetos.
 *
 * Os marcadores são `divIcon` — HTML estilizado pelo mesmo CSS do resto do
 * sistema — e não imagens. Assim eles herdam as cores de status, acompanham
 * o tema claro/escuro e não exigem nenhum arquivo de imagem.
 */

/**
 * Tom de cada status, o mesmo das etiquetas. Vira uma CLASSE (`pino-tom--x`)
 * que define a cor no CSS — e não `style="--pino-cor:..."` no HTML do
 * marcador: a Content-Security-Policy da tela em produção bloqueia estilo
 * embutido, e os pinos perdiam a cor. Visto no build de produção, não no
 * de desenvolvimento, onde a política não está ativa.
 */
function tomDoStatus(status) {
  return STATUS_ENTREGA[status]?.tom ?? "neutro";
}

function iconeBase(rotulo) {
  return L.divIcon({
    className: "",
    html: `<span class="pino pino--base" title="${rotulo}"></span>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

function iconeEntrega(status, destacado = false) {
  return L.divIcon({
    className: "",
    html: `<span class="pino pino--entrega pino-tom--${tomDoStatus(status)} ${
      destacado ? "pino--destacado" : ""
    }"></span>`,
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
}

function iconeParada(ordem, status, destacado) {
  return L.divIcon({
    className: "",
    html: `<span class="pino-ordem pino-tom--${tomDoStatus(status)} ${
      destacado ? "pino-ordem--destacado" : ""
    }">${ordem}</span>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
  });
}

export function MarcadorBase({ base }) {
  return (
    <Marker position={[base.latitude, base.longitude]} icon={iconeBase(base.rotulo ?? base.name)}>
      <Popup>
        <strong>{base.rotulo ?? base.name}</strong>
        <div className="popup__linha">Base da operação</div>
      </Popup>
    </Marker>
  );
}

export function MarcadoresEntregas({ entregas, aoSelecionar }) {
  return entregas.map((e) => (
    <Marker
      key={`e-${e.id}`}
      position={[e.latitude, e.longitude]}
      icon={iconeEntrega(e.status)}
      eventHandlers={aoSelecionar ? { click: () => aoSelecionar(e) } : undefined}
    >
      <Popup>
        <strong>{e.rotulo}</strong>
        {e.status && (
          <div className="popup__linha">{STATUS_ENTREGA[e.status]?.rotulo ?? e.status}</div>
        )}
      </Popup>
    </Marker>
  ));
}

/**
 * Trajeto de uma rota.
 *
 * Quando o provedor devolveu geometria, desenha o caminho real pela malha
 * viária. Quando não devolveu, liga as paradas com linha **tracejada** — a
 * diferença visual é deliberada: linha cheia promete um caminho que o
 * sistema conhece, e a tracejada admite que é só a ligação entre pontos.
 */
export function TrajetoRota({ rota, cor, destacada = true, aoClicar }) {
  const pontos = useMemo(() => {
    if (rota.geometry) return decodificarPolyline(rota.geometry);
    return (rota.stops ?? [])
      .filter((p) => p.latitude != null && p.longitude != null)
      .map((p) => [Number(p.latitude), Number(p.longitude)]);
  }, [rota]);

  if (pontos.length < 2) return null;

  const real = Boolean(rota.geometry);

  return (
    <Polyline
      positions={pontos}
      pathOptions={{
        color: cor,
        weight: destacada ? 4 : 3,
        // Rota não selecionada perde presença mas continua visível: sumir
        // faria a pessoa perder a noção de quantas rotas existem.
        opacity: destacada ? 0.9 : 0.25,
        dashArray: real ? undefined : "6 8",
        lineCap: "round",
        lineJoin: "round",
      }}
      eventHandlers={aoClicar ? { click: () => aoClicar(rota) } : undefined}
    />
  );
}

export function ParadasDaRota({ rota, cor, destacada = true, aoSelecionar }) {
  return (rota.stops ?? [])
    .filter((p) => p.stop_type === "ENTREGA" && p.latitude != null)
    .map((parada) => (
      <Marker
        key={`p-${parada.id}`}
        position={[Number(parada.latitude), Number(parada.longitude)]}
        icon={iconeParada(
          parada.sequence,
          parada.items?.[0]?.status ?? "PLANEJADA",
          destacada,
        )}
        opacity={destacada ? 1 : 0.45}
        eventHandlers={aoSelecionar ? { click: () => aoSelecionar(parada) } : undefined}
      >
        <Popup>
          <strong>
            {parada.sequence}. {parada.label}
          </strong>
          {parada.address && <div className="popup__linha">{parada.address}</div>}
          {parada.items?.length > 1 && (
            <div className="popup__linha">{parada.items.length} entregas nesta parada</div>
          )}
        </Popup>
      </Marker>
    ));
}

/**
 * Enquadra o mapa nos pontos informados.
 *
 * Sem isto o mapa abre num zoom fixo e a operação pode ficar fora da tela —
 * especialmente com uma entrega distante puxando a área para longe.
 */
export function AjustarLimites({ pontos, ativo = true, zoomUnico = 15 }) {
  const mapa = useMap();

  // A dependencia e o CONTEUDO dos pontos, nao o array.
  //
  // A versao anterior dependia do array, e quem chama cria um array novo a
  // cada renderizacao. O efeito era um mapa que nao deixava ninguem dar
  // zoom: no painel, que recarrega a cada 15 s, quem aproximava um bairro
  // era jogado de volta para a cidade inteira (medido: zoom 16 -> 13); no
  // cadastro, arrastar o pino para conferir o portao tirava o zoom (17 ->
  // 15) justamente quando ele era necessario.
  //
  // Ordenada para que a mesma lista vinda em outra ordem do servidor nao
  // conte como mudanca.
  const chave = (pontos ?? [])
    .filter(([lat, lon]) => Number.isFinite(lat) && Number.isFinite(lon))
    .map(([lat, lon]) => `${Number(lat).toFixed(6)},${Number(lon).toFixed(6)}`)
    .sort()
    .join("|");

  useEffect(() => {
    if (!ativo || !chave) return;
    const validos = chave.split("|").map((p) => p.split(",").map(Number));

    if (validos.length === 1) {
      mapa.setView(validos[0], zoomUnico);
      return;
    }
    mapa.fitBounds(L.latLngBounds(validos), { padding: [48, 48], maxZoom: 16 });
  }, [mapa, chave, ativo, zoomUnico]);

  return null;
}

/** Paleta das rotas no mapa. Repete a partir da sétima, que é mais do que
 *  a operação vai ter em rua ao mesmo tempo. */
export const CORES_ROTA = [
  "#5d49e6",
  "#0e7a4a",
  "#a35f06",
  "#2159bd",
  "#b82d2d",
  "#7c3aed",
];

export function corDaRota(indice) {
  return CORES_ROTA[indice % CORES_ROTA.length];
}
