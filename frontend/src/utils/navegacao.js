/**
 * Geometria da navegação: onde o motorista está AO LONGO da rota.
 *
 * A pergunta "falta quanto até virar?" não se responde em linha reta. Numa
 * rua que faz curva, o ponto da manobra pode estar a 80 m em linha reta e a
 * 300 m pela rua. Por isso a posição do GPS é projetada sobre a linha da
 * rota, e todas as distâncias são medidas ao longo dela.
 *
 * Tudo aqui é conta pura, sem React e sem rede — o que permite testar e
 * rodar a cada leitura do GPS (cerca de uma por segundo) sem custo.
 */

import { decodificarPolyline } from "./polyline";

const RAIO_TERRA_M = 6371000;
const rad = (g) => (g * Math.PI) / 180;

export function distanciaM(a, b) {
  const dLat = rad(b[0] - a[0]);
  const dLon = rad(b[1] - a[1]);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(dLon / 2) ** 2;
  return 2 * RAIO_TERRA_M * Math.asin(Math.sqrt(h));
}

/** Projeção local em metros. Numa cidade, o erro da aproximação plana é
 *  desprezível perto do erro do próprio GPS. */
function emMetros(p, origem) {
  const x = rad(p[1] - origem[1]) * RAIO_TERRA_M * Math.cos(rad(origem[0]));
  const y = rad(p[0] - origem[0]) * RAIO_TERRA_M;
  return [x, y];
}

/**
 * Prepara a rota uma vez por resposta do servidor: pontos, distância
 * acumulada até cada ponto e em que ponto cada manobra acontece.
 */
export function prepararRota(geometria, manobras = []) {
  const pontos = decodificarPolyline(geometria);
  const acumulado = [0];
  for (let i = 1; i < pontos.length; i += 1) {
    acumulado.push(acumulado[i - 1] + distanciaM(pontos[i - 1], pontos[i]));
  }

  // Cada manobra cai sobre um vértice da linha. Procura sempre para frente
  // a partir da anterior: numa rota que passa duas vezes perto do mesmo
  // cruzamento, a busca global pegaria a passagem errada.
  let desde = 0;
  const indices = manobras.map((m) => {
    let melhor = desde;
    let menor = Infinity;
    for (let i = desde; i < pontos.length; i += 1) {
      const d = distanciaM(pontos[i], [m.latitude, m.longitude]);
      if (d < menor) {
        menor = d;
        melhor = i;
      }
      if (menor < 2) break;
    }
    desde = melhor;
    return melhor;
  });

  return {
    pontos,
    acumulado,
    total: acumulado[acumulado.length - 1] ?? 0,
    indicesManobra: indices,
    manobras,
  };
}

/**
 * Onde a posição cai sobre a rota.
 *
 * Devolve quanto já foi percorrido (metros ao longo da rota) e a que
 * distância a posição está da linha — acima de algumas dezenas de metros,
 * o motorista saiu do caminho.
 *
 * `dica` é o segmento da leitura anterior. A busca começa um pouco antes
 * dela para não "voltar" a rota por causa de um GPS que oscilou, mas olha a
 * rota toda se não achar nada perto — um recálculo pode ter mudado tudo.
 */
export function projetar(rota, posicao, dica = 0) {
  const { pontos, acumulado } = rota;
  if (pontos.length < 2) {
    return { segmento: 0, percorrido: 0, desvioM: pontos.length ? distanciaM(pontos[0], posicao) : 0 };
  }

  const inicio = Math.max(0, dica - 3);
  let melhor = { segmento: inicio, percorrido: 0, desvioM: Infinity };

  const avaliar = (i) => {
    const a = pontos[i];
    const b = pontos[i + 1];
    const [bx, by] = emMetros(b, a);
    const [px, py] = emMetros(posicao, a);
    const comprimento2 = bx * bx + by * by;
    const t = comprimento2 > 0 ? Math.max(0, Math.min(1, (px * bx + py * by) / comprimento2)) : 0;
    const dx = px - t * bx;
    const dy = py - t * by;
    const desvio = Math.sqrt(dx * dx + dy * dy);
    if (desvio < melhor.desvioM) {
      melhor = {
        segmento: i,
        percorrido: acumulado[i] + t * (acumulado[i + 1] - acumulado[i]),
        desvioM: desvio,
      };
    }
  };

  for (let i = inicio; i < pontos.length - 1; i += 1) avaliar(i);
  if (melhor.desvioM > 60 && inicio > 0) {
    for (let i = 0; i < inicio; i += 1) avaliar(i);
  }
  return melhor;
}

/** Próxima manobra à frente de quem já percorreu `percorrido` metros. */
export function proximaManobra(rota, percorrido) {
  const { manobras, indicesManobra, acumulado } = rota;
  for (let i = 0; i < manobras.length; i += 1) {
    const emMetrosDaRota = acumulado[indicesManobra[i]] ?? 0;
    // "depart" é o começo: nunca é a próxima.
    if (manobras[i].tipo === "depart") continue;
    if (emMetrosDaRota > percorrido + 5) {
      return {
        indice: i,
        manobra: manobras[i],
        distanciaM: emMetrosDaRota - percorrido,
        seguinte: manobras[i + 1] ?? null,
      };
    }
  }
  return null;
}

/** "350 m", "1,2 km" — arredondado como um motorista lê. */
export function formatarDistancia(metros) {
  if (metros == null || !Number.isFinite(metros)) return "";
  if (metros < 1000) {
    const passo = metros < 100 ? 10 : 50;
    return `${Math.max(passo, Math.round(metros / passo) * passo)} m`;
  }
  return `${(metros / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} km`;
}

/** Frase falada: "Em 300 metros, vire à direita na Rua Bahia". */
export function fraseFalada(metros, instrucao) {
  if (metros == null || metros < 60) return instrucao;
  const arredondado = metros < 1000 ? Math.round(metros / 50) * 50 : null;
  const quanto = arredondado
    ? `${arredondado} metros`
    : `${(metros / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} quilômetros`;
  const frase = instrucao.charAt(0).toLowerCase() + instrucao.slice(1);
  return `Em ${quanto}, ${frase}`;
}
