import { useEffect } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";

import "leaflet/dist/leaflet.css";
import "./MapPanel.css";

/**
 * Container de mapa do Log Rotas.
 *
 * O mapa é parte do produto, não um iframe encaixado na tela: fica dentro da
 * superfície, com o mesmo raio e a mesma borda dos outros cartões, controles
 * no vocabulário do sistema e painéis flutuantes por cima.
 *
 * Toda a camada de apresentação vive aqui. Quando a Fase 4 trouxer entregas
 * geocodificadas e a Fase 7 trouxer rotas, elas entram como `children`
 * (marcadores e polilinhas) sem que este arquivo precise mudar.
 */

const CAMPO_GRANDE = [-20.4697, -54.6201];

// Base cartográfica dessaturada: a rua fica legível mas discreta, e a cor
// sobra para o que importa — rota, parada e status. Base colorida disputa
// atenção com o dado.
const BASES = {
  claro: {
    url: "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
    atribuicao:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  escuro: {
    url: "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
    atribuicao:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
};

/** O Leaflet calcula o tamanho no momento da montagem; se o container ainda
 *  estava mudando de tamanho, o mapa nasce cortado. Este ajuste corrige. */
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
  const base = BASES[tema] ?? BASES.claro;

  return (
    <div className="mapa" style={{ height: altura }}>
      <MapContainer
        center={centro}
        zoom={zoom}
        className="mapa__tela"
        zoomControl={false}
        attributionControl={false}
        scrollWheelZoom={false}
      >
        {/* A chave troca a camada ao mudar de tema; sem ela o Leaflet
            mantém os ladrilhos antigos em cache e o mapa fica claro dentro
            da interface escura. */}
        <TileLayer key={tema} url={base.url} attribution={base.atribuicao} />
        <AjustarAoContainer />
        {children}
      </MapContainer>

      {sobreposicao && <div className="mapa__sobreposicao">{sobreposicao}</div>}
      {rodape && <div className="mapa__rodape">{rodape}</div>}

      <div
        className="mapa__creditos"
        dangerouslySetInnerHTML={{ __html: base.atribuicao }}
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
