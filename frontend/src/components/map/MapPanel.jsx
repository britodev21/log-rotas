import { useEffect } from "react";
import { MapContainer, TileLayer, ZoomControl, useMap } from "react-leaflet";

import "leaflet/dist/leaflet.css";
import "./MapPanel.css";

/**
 * Container de mapa do Log Rotas.
 *
 * O mapa é parte do produto, não um iframe encaixado na tela: fica dentro da
 * superfície, com o mesmo raio e a mesma borda dos outros cartões, e com
 * painéis flutuantes por cima.
 *
 * Toda a camada de apresentação vive aqui. Marcadores e rotas entram como
 * `children` (ver `camadas.jsx`) sem que este arquivo precise mudar.
 */

const CAMPO_GRANDE = [-20.4697, -54.6201];

/**
 * Base cartográfica.
 *
 * Padrão: ladrilhos do próprio OpenStreetMap, que funcionam **sem chave de
 * API**. Foi uma troca necessária — a CARTO, usada antes, passou a exigir
 * chave e devolve os ladrilhos carimbados com "API KEY REQUIRED" em vez de
 * recusar a requisição, o que faz o problema passar despercebido em teste
 * automatizado (a resposta é HTTP 200, com um PNG válido).
 *
 * O visual dessaturado que o sistema usa é obtido por filtro CSS sobre os
 * ladrilhos (ver MapPanel.css), não pelo estilo do provedor. A rua fica
 * legível mas discreta, e a cor sobra para o que importa: rota, parada e
 * status.
 *
 * Para trocar por um provedor pago (CARTO, MapTiler, Stadia), basta definir
 * VITE_MAP_TILE_URL e VITE_MAP_ATTRIBUTION no .env do frontend — nenhuma
 * linha de código muda.
 */
const OSM_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
const OSM_ATRIBUICAO =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';

const URL_LADRILHOS = import.meta.env.VITE_MAP_TILE_URL || OSM_URL;
const ATRIBUICAO = import.meta.env.VITE_MAP_ATTRIBUTION || OSM_ATRIBUICAO;

/** O provedor já entrega estilo escuro próprio? Então o filtro não se aplica. */
const ESTILO_PROPRIO = Boolean(import.meta.env.VITE_MAP_TILE_URL);

/** O Leaflet calcula o tamanho do container na montagem; se ele ainda estava
 *  mudando de tamanho, o mapa nasce cortado. Este ajuste corrige. */
function AjustarAoContainer() {
  const mapa = useMap();
  useEffect(() => {
    const id = setTimeout(() => mapa.invalidateSize(), 80);
    const aoRedimensionar = () => mapa.invalidateSize();
    window.addEventListener("resize", aoRedimensionar);
    return () => {
      clearTimeout(id);
      window.removeEventListener("resize", aoRedimensionar);
    };
  }, [mapa]);
  return null;
}

export function MapPanel({
  tema = "claro",
  centro = CAMPO_GRANDE,
  zoom = 12,
  altura = 420,
  sobreposicao,
  rodape,
  children,
}) {
  return (
    <div
      className={`mapa mapa--${tema} ${ESTILO_PROPRIO ? "mapa--sem-filtro" : ""}`}
      style={{ height: altura }}
    >
      <MapContainer
        center={centro}
        zoom={zoom}
        className="mapa__tela"
        // O controle padrão nasce no canto superior esquerdo, exatamente
        // onde ficam as cápsulas com os números da operação. Ele é desligado
        // aqui e recolocado embaixo, à direita.
        zoomControl={false}
        attributionControl={false}
        // A roda do mouse fica desligada porque o mapa vive dentro de uma
        // página que rola: rolar a página com o ponteiro sobre o mapa daria
        // zoom em vez de descer a tela.
        scrollWheelZoom={false}
      >
        <TileLayer url={URL_LADRILHOS} attribution={ATRIBUICAO} maxZoom={19} />
        {/* Sem isto, e com a roda desabilitada, não haveria nenhuma forma de
            aproximar — o que inviabiliza marcar um ponto com precisão na
            tela de endereços. */}
        <ZoomControl position="bottomright" />
        <AjustarAoContainer />
        {children}
      </MapContainer>

      {sobreposicao && <div className="mapa__sobreposicao">{sobreposicao}</div>}
      {rodape && <div className="mapa__rodape">{rodape}</div>}

      {/* A licença do OpenStreetMap exige atribuição visível. O controle
          nativo do Leaflet destoa do sistema, então ela é reconstruída aqui. */}
      <div
        className="mapa__creditos"
        dangerouslySetInnerHTML={{ __html: ATRIBUICAO }}
      />
    </div>
  );
}

/** Cápsula flutuante com um número da operação. */
export function MapaResumo({ valor, rotulo, tom = "neutro" }) {
  return (
    <div className={`mapa-resumo mapa-resumo--${tom}`}>
      <span className="mapa-resumo__valor numero">{valor}</span>
      <span className="mapa-resumo__rotulo">{rotulo}</span>
    </div>
  );
}
