import { useCallback, useEffect, useRef, useState } from "react";

import { lerAccessToken } from "../api/storage";
import { motorista as api } from "../api/operacao";
import { distanciaM } from "../utils/navegacao";

/**
 * GPS do motorista durante a rota: uma única leitura contínua que serve a
 * dois donos — o painel do escritório (posições enviadas ao servidor) e o
 * mapa da navegação (posição na tela).
 *
 * O limite que molda tudo: é uma página web. O navegador só entrega posição
 * com ela em primeiro plano e a tela acesa. Por isso a navegação é feita
 * aqui dentro, e não no Google Maps — com outro app na frente, a página vai
 * para segundo plano e o GPS dela para. E por isso o estado é exposto: a
 * tela precisa dizer ao motorista quando o rastreamento não está
 * funcionando, em vez de fingir que está.
 */

/** Envio ao servidor. 10 s dá um caminhão que anda suave no painel sem
 *  transformar o celular num gerador de requisições. */
const INTERVALO_ENVIO_MS = 10000;
/** Pontos guardados no máximo. O GPS lê cerca de um por segundo; guardar
 *  todos seria desperdício, então só entra na fila quem andou ou esperou. */
const INTERVALO_MINIMO_PONTO_MS = 3000;
const DESLOCAMENTO_MINIMO_M = 15;
/** ~50 min de pontos a cada 3 s. Mais do que isso sem sinal, o trecho mais
 *  antigo é descartado — é o que menos importa para saber onde o caminhão
 *  está agora. */
const TAMANHO_MAXIMO_FILA = 1000;
const LOTE = 200;
/** Sem leitura nova por mais que isto, pede uma. Ver `pulso` abaixo. */
const LEITURA_FORCADA_MS = 15000;
/** Sem nada na fila por mais que isto, reenvia a última posição como sinal
 *  de vida. Bem abaixo dos 90 s em que o painel passa a dizer "sem sinal". */
const SINAL_DE_VIDA_MS = 20000;

const chaveFila = (rotaId) => `logrotas.fila-posicoes.${rotaId}`;

function lerFila(rotaId) {
  try {
    return JSON.parse(localStorage.getItem(chaveFila(rotaId)) ?? "[]");
  } catch {
    return [];
  }
}

function gravarFila(rotaId, fila) {
  try {
    if (fila.length) localStorage.setItem(chaveFila(rotaId), JSON.stringify(fila));
    else localStorage.removeItem(chaveFila(rotaId));
  } catch {
    // Armazenamento cheio ou bloqueado: a fila continua em memória.
  }
}

const numeroOuNulo = (v) => (v == null || Number.isNaN(v) ? null : v);

export function useRastreamento(rotaId, ativo) {
  const [estado, setEstado] = useState("desligado");
  const [posicao, setPosicao] = useState(null);
  const [ultimoEnvio, setUltimoEnvio] = useState(null);
  const [pendentes, setPendentes] = useState(0);

  const fila = useRef([]);
  const enviando = useRef(false);
  const ultimoNaFila = useRef(null);
  const ultimaLeitura = useRef(0);
  const ultimaPosicao = useRef(null);
  const ultimoEnfileirado = useRef(0);

  const enviar = useCallback(async () => {
    if (!rotaId || enviando.current || fila.current.length === 0) return;
    enviando.current = true;
    const lote = fila.current.slice(0, LOTE);
    try {
      await api.posicoes(rotaId, lote);
      fila.current = fila.current.slice(lote.length);
      setUltimoEnvio(new Date());
    } catch (e) {
      // Sem rede: os pontos ficam na fila e vão no próximo ciclo. Não é
      // erro para mostrar ao motorista a cada 10 s.
      console.warn("Posições não enviadas; ficam na fila", e?.message);
    } finally {
      enviando.current = false;
      gravarFila(rotaId, fila.current);
      setPendentes(fila.current.length);
    }
  }, [rotaId]);

  /** Último envio antes de a página congelar. `keepalive` deixa a
   *  requisição terminar mesmo com a página indo para segundo plano. */
  const enviarAoSair = useCallback(() => {
    if (!rotaId || fila.current.length === 0) return;
    const lote = fila.current.slice(0, LOTE);
    try {
      fetch(`/api/v1/motorista/rotas/${rotaId}/posicoes`, {
        method: "POST",
        keepalive: true,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${lerAccessToken()}`,
        },
        body: JSON.stringify({ posicoes: lote }),
      }).then((r) => {
        if (r.ok) {
          fila.current = fila.current.slice(lote.length);
          gravarFila(rotaId, fila.current);
          setPendentes(fila.current.length);
        }
      });
    } catch {
      // A fila já está gravada no aparelho; vai no próximo envio.
    }
  }, [rotaId]);

  useEffect(() => {
    if (!ativo || !rotaId) {
      setEstado("desligado");
      return undefined;
    }
    if (!window.isSecureContext) {
      // HTTP fora do localhost: o navegador nem pergunta. Acontece ao abrir
      // pelo IP da rede local num celular — precisa de HTTPS.
      setEstado("inseguro");
      return undefined;
    }
    if (!navigator.geolocation) {
      setEstado("indisponivel");
      return undefined;
    }

    fila.current = lerFila(rotaId);
    setPendentes(fila.current.length);
    setEstado("aguardando");

    const aoLer = (p) => {
      ultimaLeitura.current = Date.now();
      const agora = {
        latitude: p.coords.latitude,
        longitude: p.coords.longitude,
        precisao_m: numeroOuNulo(p.coords.accuracy),
        velocidade_mps: numeroOuNulo(p.coords.speed),
        direcao_graus: numeroOuNulo(p.coords.heading),
        registrada_em: new Date(p.timestamp).toISOString(),
      };
      setPosicao(agora);
      ultimaPosicao.current = agora;
      setEstado("ativo");

      const anterior = ultimoNaFila.current;
      const passou = anterior ? p.timestamp - anterior.quando : Infinity;
      const andou = anterior
        ? distanciaM([anterior.latitude, anterior.longitude], [agora.latitude, agora.longitude])
        : Infinity;
      if (passou >= INTERVALO_MINIMO_PONTO_MS || andou >= DESLOCAMENTO_MINIMO_M) {
        fila.current.push(agora);
        if (fila.current.length > TAMANHO_MAXIMO_FILA) {
          fila.current = fila.current.slice(-TAMANHO_MAXIMO_FILA);
        }
        ultimoNaFila.current = { ...agora, quando: p.timestamp };
        ultimoEnfileirado.current = Date.now();
        setPendentes(fila.current.length);
      }
    };

    const aoFalhar = (e) => {
      if (e.code === 1) setEstado("negado");
      // Sem sinal de GPS (código 2 ou 3): continua esperando a próxima
      // leitura; o estado "aguardando" já diz isso à tela.
    };

    const vigia = navigator.geolocation.watchPosition(aoLer, aoFalhar, {
      enableHighAccuracy: true,
      maximumAge: 5000,
      timeout: 20000,
    });
    const ciclo = setInterval(enviar, INTERVALO_ENVIO_MS);

    // O watchPosition só avisa quando a posição MUDA. Com o aparelho parado
    // — semáforo, uma instalação de uma hora, um computador sem GPS — ele
    // fica mudo, nada é enviado, e o escritório via "sem sinal" num caminhão
    // que estava só parado. Aqui, se o GPS ficar calado, pede-se uma
    // leitura nova: é uma medição de verdade, com a hora de verdade, e o
    // painel passa a mostrar "parado".
    //
    // Nem todo aparelho entrega hora nova numa leitura forçada (computador
    // sem GPS nunca entrega). Por isso, se nada entrou na fila há 20 s, a
    // última posição vai de novo, com a hora ORIGINAL da medição: o servidor
    // reconhece a repetição, não grava linha nova e só renova o contato. O
    // painel fica certo nas duas perguntas: "está vivo?" (sim) e "quão
    // velha é a posição?" (a idade real).
    const pulso = setInterval(() => {
      const agora = Date.now();
      if (agora - ultimaLeitura.current >= LEITURA_FORCADA_MS) {
        navigator.geolocation.getCurrentPosition(aoLer, aoFalhar, {
          enableHighAccuracy: true,
          maximumAge: 0,
          timeout: 10000,
        });
      }
      if (
        ultimaPosicao.current &&
        fila.current.length === 0 &&
        agora - ultimoEnfileirado.current >= SINAL_DE_VIDA_MS
      ) {
        fila.current.push(ultimaPosicao.current);
        ultimoEnfileirado.current = agora;
        setPendentes(fila.current.length);
      }
    }, 5000);

    const aoMudarVisibilidade = () => {
      if (document.visibilityState === "hidden") enviarAoSair();
      else enviar();
    };
    document.addEventListener("visibilitychange", aoMudarVisibilidade);
    window.addEventListener("pagehide", enviarAoSair);

    return () => {
      navigator.geolocation.clearWatch(vigia);
      clearInterval(ciclo);
      clearInterval(pulso);
      document.removeEventListener("visibilitychange", aoMudarVisibilidade);
      window.removeEventListener("pagehide", enviarAoSair);
      gravarFila(rotaId, fila.current);
      enviar();
    };
  }, [ativo, rotaId, enviar, enviarAoSair]);

  return { estado, posicao, ultimoEnvio, pendentes, enviarAgora: enviar };
}
