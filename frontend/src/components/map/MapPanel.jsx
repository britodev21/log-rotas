import { useEffect, useState } from "react";
import { MapContainer, TileLayer, ZoomControl, useMap } from "react-leaflet";
import { Layers, Map as MapaIcone } from "lucide-react";

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
/**
 * Até onde a base cinza tem desenho de verdade: zoom 16. Medido em
 * 21/09/2026 no centro e num bairro afastado — do 17 em diante a Esri
 * devolve, para qualquer lugar, o mesmo ladrilho de 2.521 bytes escrito "Map
 * data not yet available". Com HTTP 200, como a CARTO: só aparece olhando.
 *
 * Com `maxNativeZoom`, o Leaflet amplia os ladrilhos do 16 quando a tela
 * pede 17, 18 ou 19. Fica menos nítido, mas é o mapa — e não um aviso em
 * inglês cobrindo a navegação do motorista, que usa zoom 17.
 */
const ZOOM_NATIVO_CINZA = 16;

const BASES = {
  claro: {
    url: `${ESRI}/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}`,
    rotulos: `${ESRI}/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}`,
    atribuicao: ESRI_ATRIBUICAO,
    zoomNativo: ZOOM_NATIVO_CINZA,
  },
  escuro: {
    url: `${ESRI}/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`,
    rotulos: `${ESRI}/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}`,
    atribuicao: ESRI_ATRIBUICAO,
    zoomNativo: ZOOM_NATIVO_CINZA,
  },
};

/**
 * Satélite.
 *
 * Existe por um motivo específico e medido: o OpenStreetMap tem número de
 * porta em cerca de 530 prédios de Campo Grande, numa cidade de ~900 mil
 * habitantes. Nenhum geocodificador gratuito acha o número — quem acha é a
 * pessoa, olhando o telhado, o portão e a esquina.
 *
 * Sem imagem de satélite, "marque o ponto exato" é um pedido impossível:
 * num mapa cinza todas as casas do quarteirão são o mesmo retângulo.
 *
 * Limites conferidos na fonte em 2026-09-21, no centro e num bairro
 * afastado: imagem real até o zoom 19; no 20 a Esri devolve um ladrilho
 * chapado de 2.521 bytes. Por isso `maxZoom` é 19 aqui — deixar 20 daria
 * uma tela cinza sem explicação.
 *
 * Os rótulos de rua vêm de World_Transportation. A camada de nomes de
 * lugar (World_Boundaries_and_Places) foi testada e volta vazia nestes
 * zooms; carregá-la seria requisição sem retorno.
 */
const SATELITE = {
  url: "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
  rotulos:
    "https://services.arcgisonline.com/ArcGIS/rest/services/Reference/World_Transportation/MapServer/tile/{z}/{y}/{x}",
  atribuicao: "Imagens &copy; Esri, Maxar, Earthstar Geographics",
  zoomMaximo: 19,
  zoomNativo: 19,
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
  // Ligado onde o objetivo é marcar um ponto na porta certa. Fica desligado
  // no painel e no acompanhamento de rota, onde a imagem só polui.
  permitirSatelite = false,
  children,
}) {
  const [satelite, setSatelite] = useState(false);

  const cartografia = URL_CONFIGURADA
    ? { url: URL_CONFIGURADA, atribuicao: ATRIBUICAO_CONFIGURADA ?? "" }
    : (BASES[tema] ?? BASES.claro);
  const base = satelite ? SATELITE : cartografia;
  const zoomMaximo = base.zoomMaximo ?? 19;
  const zoomNativo = base.zoomNativo;
  const camada = satelite ? "satelite" : tema;

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
        <TileLayer
          key={camada}
          url={base.url}
          attribution={base.atribuicao}
          maxZoom={zoomMaximo}
          maxNativeZoom={zoomNativo}
        />
        {/* Rótulos por cima dos marcadores não: `pane="shadowPane"` mantém
            os nomes acima do mapa e abaixo das paradas, que precisam ficar
            sempre clicáveis. */}
        {base.rotulos && (
          <TileLayer
            key={`${camada}-rotulos`}
            url={base.rotulos}
            maxZoom={zoomMaximo}
            maxNativeZoom={zoomNativo}
            pane="shadowPane"
          />
        )}
        {/* Sem isto, e com a roda desabilitada, não haveria nenhuma forma de
            aproximar — o que inviabiliza marcar um ponto com precisão na
            tela de endereços. */}
        <ZoomControl position="bottomright" />
        <AjustarAoContainer />
        {children}
      </MapContainer>

      {permitirSatelite && (
        <button
          type="button"
          className="mapa__vista"
          onClick={() => setSatelite((v) => !v)}
          aria-pressed={satelite}
          title={
            satelite
              ? "Voltar ao mapa de ruas"
              : "Ver por satélite para achar o prédio certo"
          }
        >
          {satelite ? <MapaIcone size={14} strokeWidth={2} /> : <Layers size={14} strokeWidth={2} />}
          <span>{satelite ? "Mapa" : "Satélite"}</span>
        </button>
      )}

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
