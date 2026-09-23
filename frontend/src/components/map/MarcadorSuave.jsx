import { useEffect, useRef } from "react";
import { useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";

/**
 * O veículo deslizando entre as leituras do GPS.
 *
 * O aparelho entrega uma posição a cada poucos segundos. Pôr o marcador
 * direto em cada leitura faz o caminhão PULAR de ponto em ponto — foi o que
 * apareceu dirigindo até a esquina. Waze e Google Maps fazem o que este
 * componente faz: deslizam da leitura anterior até a nova, no tempo que
 * separou as duas, e giram a seta pelo caminho angular mais curto.
 *
 * O que ele **não** faz: adivinhar onde o caminhão está depois da última
 * leitura. Entre dois pontos medidos, deslizar é desenho — o caminhão
 * esteve nos dois. Adiante do último, seria invenção, e o escritório veria
 * um caminhão onde ele não está.
 *
 * Duas salvaguardas: salto grande (GPS que "pula" um quarteirão) entra
 * direto, sem animação de travessia; e o laço de animação para junto com a
 * tela, porque `requestAnimationFrame` não roda com o aparelho bloqueado.
 */

/** Acima disto não é movimento: é correção de GPS. Entra sem deslizar. */
const SALTO_M = 250;
/** Limites da duração do deslize, em ms. */
const MINIMO_MS = 350;
const MAXIMO_MS = 3000;
/** Parte central da tela onde o veículo anda sem a câmera ir atrás. */
const MIOLO = 0.22;
/** Intervalo mínimo entre dois deslocamentos da câmera, em ms. */
const ESPERA_PAN_MS = 900;

function metrosEntre(a, b) {
  const R = 6371000;
  const rad = Math.PI / 180;
  const dLat = (b[0] - a[0]) * rad;
  const dLon = (b[1] - a[1]) * rad;
  const lat = ((a[0] + b[0]) / 2) * rad;
  const x = dLon * Math.cos(lat);
  return Math.sqrt(dLat * dLat + x * x) * R;
}

/** Diferença de ângulo pelo caminho curto: de 350° para 10° são +20°. */
function diferencaAngular(de, para) {
  return ((((para - de) % 360) + 540) % 360) - 180;
}

export function MarcadorSuave({
  alvo,
  direcao,
  criarIcone,
  seguir = false,
  zoomAoSeguir,
  aoArrastar,
  zIndexOffset = 1000,
}) {
  const mapa = useMap();
  const marcador = useRef(null);
  const posicao = useRef(null); // onde o marcador está agora, no desenho
  const origem = useRef(null);
  const destino = useRef(null);
  const anguloAtual = useRef(0);
  const anguloAlvo = useRef(0);
  const inicio = useRef(0);
  const duracao = useRef(MINIMO_MS);
  const ultimaLeitura = useRef(0);
  const quadro = useRef(null);
  const ultimoPan = useRef(0);
  const seguindo = useRef(seguir);

  useMapEvents({ dragstart: () => aoArrastar?.() });

  seguindo.current = seguir;

  useEffect(() => {
    if (!seguir || !posicao.current) return;
    ultimoPan.current = performance.now();
    mapa.panTo(posicao.current, { animate: true, duration: 0.6 });
  }, [seguir, mapa]);

  // O marcador é criado uma vez e movido pela API do Leaflet. Re-renderizar
  // o React a cada quadro para mover um ícone seria trabalho perdido — e a
  // 60 quadros por segundo, perdido o tempo todo.
  useEffect(() => {
    const icone = criarIcone();
    marcador.current = L.marker([0, 0], { icon: icone, zIndexOffset, interactive: false });
    marcador.current.addTo(mapa);
    return () => {
      marcador.current?.remove();
      marcador.current = null;
    };
    // criarIcone é estável por construção (ver NavegacaoMotorista).
  }, [mapa, criarIcone, zIndexOffset]);

  // Leitura nova: define para onde deslizar e em quanto tempo.
  useEffect(() => {
    if (!alvo || !marcador.current) return;
    const agora = performance.now();

    if (!posicao.current || metrosEntre(posicao.current, alvo) > SALTO_M) {
      posicao.current = alvo;
      origem.current = alvo;
      destino.current = alvo;
      marcador.current.setLatLng(alvo);
      if (seguindo.current) mapa.setView(alvo, zoomAoSeguir ?? mapa.getZoom(), { animate: false });
    } else {
      origem.current = posicao.current;
      destino.current = alvo;
      inicio.current = agora;
      // O deslize dura o mesmo que o intervalo entre as duas leituras: é o
      // que faz o movimento na tela ter a velocidade do movimento real.
      const intervalo = ultimaLeitura.current ? agora - ultimaLeitura.current : MINIMO_MS;
      duracao.current = Math.min(MAXIMO_MS, Math.max(MINIMO_MS, intervalo));
    }
    ultimaLeitura.current = agora;
  }, [alvo, mapa, zoomAoSeguir]);

  useEffect(() => {
    if (direcao == null) return;
    anguloAlvo.current = direcao;
  }, [direcao]);

  useEffect(() => {
    /**
     * A câmera só corre atrás quando o veículo sai do miolo da tela.
     *
     * Mover o mapa a cada quadro parece o certo e é o contrário: medido na
     * tela de navegação, derrubava para 16 quadros por segundo, porque cada
     * movimento reposiciona todos os ladrilhos. O veículo desliza a cada
     * quadro (é só o ícone); o mapa se desloca de vez em quando, com a
     * animação do próprio Leaflet.
     */
    const recentrar = () => {
      const agora = performance.now();
      if (agora - ultimoPan.current < ESPERA_PAN_MS) return;
      const tela = mapa.getSize();
      const ponto = mapa.latLngToContainerPoint(posicao.current);
      const foraDoMiolo =
        Math.abs(ponto.x - tela.x / 2) > tela.x * MIOLO ||
        Math.abs(ponto.y - tela.y / 2) > tela.y * MIOLO;
      if (!foraDoMiolo) return;
      ultimoPan.current = agora;
      mapa.panTo(posicao.current, { animate: true, duration: 0.9, easeLinearity: 0.4 });
    };

    const passo = () => {
      quadro.current = requestAnimationFrame(passo);
      const marca = marcador.current;
      if (!marca || !destino.current) return;

      if (origem.current && destino.current !== origem.current) {
        const avanco = Math.min(1, (performance.now() - inicio.current) / duracao.current);
        posicao.current = [
          origem.current[0] + (destino.current[0] - origem.current[0]) * avanco,
          origem.current[1] + (destino.current[1] - origem.current[1]) * avanco,
        ];
        marca.setLatLng(posicao.current);
        if (seguindo.current) recentrar();
      }

      // A seta gira acompanhando, e não de uma vez: virar 90° num quadro é
      // o mesmo salto do marcador, só que no ângulo.
      const falta = diferencaAngular(anguloAtual.current, anguloAlvo.current);
      if (Math.abs(falta) > 0.5) {
        anguloAtual.current += falta * 0.18;
        const seta = marca.getElement()?.querySelector(".js-girar");
        // Pelo CSSOM, não por atributo style: a CSP da tela recusa estilo
        // embutido no HTML, mas isto é script mexendo no elemento.
        if (seta) seta.style.transform = `rotate(${anguloAtual.current.toFixed(1)}deg)`;
      }
    };

    quadro.current = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro.current);
  }, [mapa]);

  return null;
}
