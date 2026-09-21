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
 * Padrão: as bases cinza da Esri, que funcionam **sem chave de API** e foram
 * desenhadas justamente para receber dado por cima — a rua fica legível mas
 * discreta, e a cor sobra para rota, parada e status.
 *
 * A versão anterior usava ladrilhos do OpenStreetMap com filtro CSS para
 * dessaturar. Funcionava, mas ficava turvo: o filtro inverte os rótulos
 * junto com o mapa, e texto invertido nunca fica bom. Aqui os rótulos já
 * são desenhados para fundo claro ou escuro.
 *
 * Antes disto a base era da CARTO, que passou a exigir chave e devolve os
 * ladrilhos carimbados com "API KEY REQUIRED" — com HTTP 200 e um PNG
 * válido, o que faz o defeito passar por qualquer verificação automática.
 * Por isso toda troca de provedor aqui é conferida na tela, não no código
 * de resposta.
 *
 * Para trocar por um provedor pago, defina VITE_MAP_TILE_URL e
 * VITE_MAP_ATTRIBUTION no .env do frontend — nenhuma linha de código muda.
 */
const ESRI = "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas";
const ESRI_ATRIBUICAO = "Ladrilhos &copy; Esri &middot; dados &copy; OpenStreetMap";

/**
 * A Esri separa o mapa em duas camadas: o desenho (ruas, quadras, água) e os
 * rótulos (nomes de rua, bairro, ponto de referência).
 *
 * Carregar só a primeira deixa o mapa bonito e inútil — sem nome nenhum,
 * quem olha não reconhece onde a entrega fica. As duas juntas dão o
 * resultado certo: base discreta, rótulo nítido, desenhado para o fundo
 * claro ou escuro em vez de invertido por filtro.
 */
const BASES = {
  claro: {
    url: `${ESRI}/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}`,
    rotulos: `${ESRI}/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}`,
    atribuicao: ESRI_ATRIBUICAO,
  },
  escuro: {
    url: `${ESRI}/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`,
    rotulos: `${ESRI}/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}`,
    atribuicao: ESRI_ATRIBUICAO,
  },
};

const URL_CONFIGURADA = import.meta.env.VITE_MAP_TILE_URL;
const ATRIBUICAO_CONFIGURADA = import.meta.env.VITE_MAP_ATTRIBUTION;

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
  const base = URL_CONFIGURADA
    ? { url: URL_CONFIGURADA, atribuicao: ATRIBUICAO_CONFIGURADA ?? "" }
    : (BASES[tema] ?? BASES.claro);

  return (
    <div className={`mapa mapa--${tema}`} style={{ height: altura }}>
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
        {/* A chave troca a camada ao mudar de tema; sem ela o Leaflet mantém
            os ladrilhos antigos em cache e o mapa fica claro dentro da
            interface escura. */}
        <TileLayer key={tema} url={base.url} attribution={base.atribuicao} maxZoom={19} />
        {/* Rótulos por cima dos marcadores não: `pane="shadowPane"` mantém
            os nomes acima do mapa e abaixo das paradas, que precisam ficar
            sempre clicáveis. */}
        {base.rotulos && (
          <TileLayer key={`${tema}-rotulos`} url={base.rotulos} maxZoom={19} pane="shadowPane" />
        )}
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
