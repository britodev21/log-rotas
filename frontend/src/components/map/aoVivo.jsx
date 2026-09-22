import { Fragment, useEffect, useRef, useState } from "react";
import { Marker, Polyline, Tooltip } from "react-leaflet";
import L from "leaflet";

import { distanciaM } from "../../utils/navegacao";

/**
 * Caminhões em rota, no mapa do escritório.
 *
 * O que faz parecer "ao vivo" não é a frequência da consulta: é o marcador
 * deslizar entre uma posição e a seguinte no mesmo ritmo em que o GPS as
 * mediu. Um ponto que pula a cada 10 s parece travado; o mesmo ponto
 * andando em 10 s parece um caminhão.
 *
 * O que ele não esconde: a posição tem alguns segundos de atraso (o celular
 * manda em lote a cada ~10 s), e sem sinal o caminhão fica cinza, parado
 * onde foi visto pela última vez, com o tempo desde então.
 */

/** Salto maior que isto não é animado: é o sinal voltando depois de muito
 *  tempo, e deslizar atravessando a cidade seria desenhar um trajeto que
 *  ninguém fez. */
const SALTO_SEM_ANIMACAO_M = 1500;
const ANIMACAO_MIN_MS = 800;
const ANIMACAO_MAX_MS = 10000;

const icones = new Map();
function iconeCaminhao(cor, direcao, semSinal) {
  const graus = direcao == null ? null : Math.round(direcao / 10) * 10;
  const chave = `${cor}|${graus}|${semSinal}`;
  if (!icones.has(chave)) {
    const fundo = semSinal ? "#8a93a6" : cor;
    const seta =
      graus == null
        ? `<circle cx="16" cy="16" r="4" fill="#fff"/>`
        : `<path d="M16 7 L21.5 21 L16 18 L10.5 21 Z" fill="#fff"
                 transform="rotate(${graus} 16 16)"/>`;
    const anel = semSinal
      ? `<circle cx="16" cy="16" r="14.5" fill="none" stroke="${fundo}" stroke-width="2" stroke-dasharray="3 3"/>`
      : `<circle cx="16" cy="16" r="15" fill="${fundo}" opacity="0.18"/>`;
    icones.set(
      chave,
      L.divIcon({
        className: "caminhao-ao-vivo",
        html: `<svg viewBox="0 0 32 32" width="32" height="32">
                 ${anel}
                 <circle cx="16" cy="16" r="11" fill="${fundo}" stroke="#fff" stroke-width="2.5"/>
                 ${seta}
               </svg>`,
        iconSize: [32, 32],
        iconAnchor: [16, 16],
        tooltipAnchor: [0, 14],
      }),
    );
  }
  return icones.get(chave);
}

/**
 * Marcador que desliza até a posição nova. A duração é o intervalo entre
 * as duas leituras do GPS: o caminhão anda no painel na velocidade em que
 * andou na rua.
 */
function MarcadorQueDesliza({ posicao, medidaEm, icone, children }) {
  const ref = useRef(null);
  const [inicial] = useState(posicao);
  const exibida = useRef(posicao);
  const quandoAnterior = useRef(medidaEm);

  useEffect(() => {
    const marcador = ref.current;
    if (!marcador) return undefined;
    const de = exibida.current;
    const para = posicao;
    const intervalo = medidaEm && quandoAnterior.current
      ? new Date(medidaEm) - new Date(quandoAnterior.current)
      : ANIMACAO_MIN_MS;
    quandoAnterior.current = medidaEm;

    if (!de || distanciaM(de, para) > SALTO_SEM_ANIMACAO_M || distanciaM(de, para) < 0.5) {
      marcador.setLatLng(para);
      exibida.current = para;
      return undefined;
    }

    const duracao = Math.min(ANIMACAO_MAX_MS, Math.max(ANIMACAO_MIN_MS, intervalo));
    const inicio = performance.now();
    let quadro;
    const passo = (agora) => {
      const t = Math.min(1, (agora - inicio) / duracao);
      const ponto = [de[0] + (para[0] - de[0]) * t, de[1] + (para[1] - de[1]) * t];
      marcador.setLatLng(ponto);
      exibida.current = ponto;
      if (t < 1) quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
    // Anima quando a posição muda de fato, não a cada consulta igual.
  }, [posicao[0], posicao[1]]);

  return (
    <Marker ref={ref} position={inicial} icon={icone} zIndexOffset={1000}>
      {children}
    </Marker>
  );
}

/** Direção pelo rastro, quando o GPS não informa — muitos celulares não
 *  informam em baixa velocidade, e sem ela a seta vira um ponto. */
function direcaoPeloRastro(rastro) {
  for (let i = rastro.length - 1; i > 0; i -= 1) {
    const de = rastro[i - 1];
    const para = rastro[rastro.length - 1];
    if (distanciaM(de, para) > 8) {
      const [a, b, c, d] = [de[0], de[1], para[0], para[1]].map((g) => (g * Math.PI) / 180);
      const y = Math.sin(d - b) * Math.cos(c);
      const x = Math.cos(a) * Math.sin(c) - Math.sin(a) * Math.cos(c) * Math.cos(d - b);
      return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
    }
  }
  return null;
}

function tempoSemSinal(segundos) {
  if (segundos == null) return "";
  if (segundos < 90) return `há ${segundos} s`;
  return `há ${Math.round(segundos / 60)} min`;
}

export function CaminhoesAoVivo({ rotas, corDe, destacada }) {
  return rotas.map((r) => {
    if (!r.posicao) return null;
    const cor = corDe(r.rota_id);
    const semSinal = r.situacao === "SEM_SINAL";
    const apagada = destacada != null && destacada !== r.rota_id;
    const posicao = [r.posicao.latitude, r.posicao.longitude];
    const primeiroNome = (r.motorista ?? "").split(" ")[0] || "Motorista";

    return (
      <Fragment key={r.rota_id}>
        {r.rastro.length > 1 && (
          <Polyline
            positions={r.rastro}
            pathOptions={{ color: cor, weight: 4, opacity: apagada ? 0.15 : 0.55 }}
          />
        )}
        <MarcadorQueDesliza
          posicao={posicao}
          medidaEm={r.posicao.registrada_em}
          icone={iconeCaminhao(
            cor,
            r.posicao.direcao_graus ?? direcaoPeloRastro(r.rastro),
            semSinal,
          )}
        >
          <Tooltip
            permanent
            direction="bottom"
            className="caminhao-rotulo"
            opacity={apagada ? 0.4 : 1}
          >
            {primeiroNome}
            {semSinal && ` · sem sinal ${tempoSemSinal(r.idade_s)}`}
          </Tooltip>
        </MarcadorQueDesliza>
      </Fragment>
    );
  });
}
