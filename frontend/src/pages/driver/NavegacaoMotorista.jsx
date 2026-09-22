import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Marker, Polyline, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import {
  ArrowUp,
  ArrowUpLeft,
  ArrowUpRight,
  CornerUpLeft,
  CornerUpRight,
  Crosshair,
  Flag,
  LocateFixed,
  MapPin,
  RotateCcw,
  Undo2,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { motorista as api } from "../../api/operacao";
import { MapPanel } from "../../components/map";
import { Badge, Button, Spinner } from "../../components/ui";
import { useTheme } from "../../hooks/useTheme";
import { hora } from "../../utils/formato";
import {
  distanciaM,
  formatarDistancia,
  fraseFalada,
  prepararRota,
  projetar,
  proximaManobra,
} from "../../utils/navegacao";
import "./navegacao.css";

/**
 * Navegação curva a curva, dentro do Log Rotas.
 *
 * Substitui o botão que abria o Google Maps. Não por capricho: com o Google
 * Maps na frente, esta página ia para segundo plano e o navegador parava o
 * GPS dela — o escritório perdia o caminhão justamente enquanto ele andava.
 *
 * O que ela faz:
 * - segue o caminhão no mapa, com a rota até a próxima parada;
 * - mostra e FALA a próxima manobra, com a distância medida pela rua;
 * - recalcula sozinha quando o motorista sai do caminho;
 * - avisa a chegada, mas NÃO registra sozinha: quem diz "cheguei" é o
 *   motorista, porque chegar na rua não é o mesmo que chegar no cliente.
 *
 * O que ela não faz, e a tela não finge: faixa de rolamento, radar, e —
 * sem trânsito configurado — desvio de congestionamento.
 */

/** Fora da linha da rota por mais que isto, em leituras seguidas, é desvio. */
const DESVIO_M = 50;
const LEITURAS_PARA_DESVIO = 3;
/** Intervalo mínimo entre recálculos: um GPS ruim não pode virar uma
 *  enxurrada de pedidos ao servidor. */
const RECALCULO_MIN_MS = 15000;
/** Perto disto do ponto de chegada, a tela oferece registrar a chegada. */
const CHEGADA_M = 40;
/** Distâncias em que a voz anuncia a próxima manobra. */
const AVISO_LONGE_M = 400;
const AVISO_PERTO_M = 80;

const CHAVE_VOZ = "logrotas.voz";

function iconeDaManobra(m) {
  if (!m) return ArrowUp;
  if (m.tipo === "arrive") return Flag;
  if (m.tipo === "roundabout" || m.tipo === "rotary" || m.tipo === "roundabout turn") {
    return RotateCcw;
  }
  switch (m.modificador) {
    case "uturn":
      return Undo2;
    case "left":
    case "sharp left":
      return CornerUpLeft;
    case "right":
    case "sharp right":
      return CornerUpRight;
    case "slight left":
      return ArrowUpLeft;
    case "slight right":
      return ArrowUpRight;
    default:
      return ArrowUp;
  }
}

function rumo(de, para) {
  const [lat1, lon1, lat2, lon2] = [de[0], de[1], para[0], para[1]].map((g) => (g * Math.PI) / 180);
  const y = Math.sin(lon2 - lon1) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(lon2 - lon1);
  return ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
}

const iconesVeiculo = new Map();
function iconeVeiculo(direcao) {
  // Arredonda para não criar um ícone novo a cada grau: o Leaflet troca o
  // elemento inteiro quando o ícone muda.
  const chave = direcao == null ? "sem" : Math.round(direcao / 5) * 5;
  if (!iconesVeiculo.has(chave)) {
    const seta =
      chave === "sem"
        ? `<span class="nav-veiculo__ponto"></span>`
        : // Atributo transform, e nao style="": a CSP da tela nao aceita estilo
          // embutido em HTML gerado.
          `<svg viewBox="0 0 24 24" width="34" height="34">
             <g transform="rotate(${chave} 12 12)">
               <path d="M12 2.5 L19.5 20.5 L12 16.5 L4.5 20.5 Z" fill="currentColor"
                     stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/>
             </g>
           </svg>`;
    iconesVeiculo.set(
      chave,
      L.divIcon({ className: "nav-veiculo", html: seta, iconSize: [34, 34], iconAnchor: [17, 17] }),
    );
  }
  return iconesVeiculo.get(chave);
}

const iconeDestino = L.divIcon({
  className: "nav-destino",
  html: `<span class="nav-destino__pino"></span>`,
  iconSize: [22, 22],
  iconAnchor: [11, 11],
});

/** Mantém o caminhão no centro até a pessoa arrastar o mapa. */
function Seguir({ posicao, ativo, aoSoltar }) {
  const mapa = useMap();
  useMapEvents({ dragstart: aoSoltar });
  useEffect(() => {
    if (!ativo || !posicao) return;
    const zoom = mapa.getZoom() < 16 ? 17 : mapa.getZoom();
    mapa.setView(posicao, zoom, { animate: true });
  }, [mapa, posicao, ativo]);
  return null;
}

function falar(texto) {
  if (!("speechSynthesis" in window) || !texto) return;
  const fala = new SpeechSynthesisUtterance(texto);
  fala.lang = "pt-BR";
  const voz = window.speechSynthesis
    .getVoices()
    .find((v) => v.lang?.toLowerCase().replace("_", "-").startsWith("pt-br"));
  if (voz) fala.voice = voz;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(fala);
}

function lerPreferenciaVoz() {
  try {
    return localStorage.getItem(CHAVE_VOZ) !== "desligada";
  } catch {
    return true;
  }
}

export function NavegacaoMotorista({ rota, rastreio, tela, agindo, aoSair, aoRegistrarChegada }) {
  const { tema } = useTheme();
  const posicao = rastreio.posicao;
  // Mesma referência enquanto a leitura do GPS não muda: o mapa só se move
  // quando o caminhão se move.
  const ponto = useMemo(
    () => (posicao ? [posicao.latitude, posicao.longitude] : null),
    [posicao],
  );

  const [nav, setNav] = useState(null);
  const [erro, setErro] = useState("");
  const [calculando, setCalculando] = useState(false);
  const [seguir, setSeguir] = useState(true);
  const [voz, setVoz] = useState(lerPreferenciaVoz);

  const pedidoEm = useRef(0);
  const leiturasFora = useRef(0);
  const dica = useRef(0);
  const anunciado = useRef(new Set());
  const anterior = useRef(null);
  const direcaoCalculada = useRef(null);

  // A parada que a navegação deve buscar, pelo mesmo critério do servidor:
  // a primeira ainda aberta, e a base quando as entregas acabarem.
  const alvoId = useMemo(() => {
    const abertas = [...rota.stops]
      .sort((a, b) => a.sequence - b.sequence)
      .filter((s) => s.stop_type !== "BASE_SAIDA" && ["PENDENTE", "CHEGOU"].includes(s.status));
    return abertas[0]?.id ?? null;
  }, [rota.stops]);

  const buscar = useCallback(
    async (p) => {
      if (!p) return;
      pedidoEm.current = Date.now();
      setCalculando(true);
      try {
        const resposta = await api.navegacao(rota.id, p[0], p[1]);
        setNav(resposta);
        setErro("");
        dica.current = 0;
        leiturasFora.current = 0;
        anunciado.current = new Set();
      } catch (e) {
        console.error("Falha ao calcular a navegação", e);
        setErro(mensagemDeErro(e, "Não foi possível calcular a rota agora."));
      } finally {
        setCalculando(false);
      }
    },
    [rota.id],
  );

  // Primeira rota assim que houver GPS, e outra sempre que a parada mudar
  // (depois de registrar uma chegada ou uma entrega).
  const alvoBuscado = useRef(null);
  useEffect(() => {
    if (!ponto || alvoId == null || alvoBuscado.current === alvoId) return;
    alvoBuscado.current = alvoId;
    buscar(ponto);
  }, [ponto, alvoId, buscar]);

  const preparada = useMemo(
    () => (nav?.geometria ? prepararRota(nav.geometria, nav.manobras) : null),
    [nav],
  );

  const projecao = preparada && ponto ? projetar(preparada, ponto, dica.current) : null;
  const proxima = projecao ? proximaManobra(preparada, projecao.percorrido) : null;

  const destino = nav?.latitude_chegada != null ? [nav.latitude_chegada, nav.longitude_chegada] : null;
  const restanteM = projecao
    ? Math.max(0, preparada.total - projecao.percorrido)
    : destino && ponto
      ? distanciaM(ponto, destino)
      : null;
  const restanteS =
    nav && restanteM != null && nav.distancia_m > 0
      ? (nav.duracao_s * restanteM) / nav.distancia_m
      : nav?.duracao_s ?? null;
  const chegada = restanteS != null ? new Date(Date.now() + restanteS * 1000) : null;
  const chegou = restanteM != null && restanteM <= CHEGADA_M;
  const parada = nav?.parada;
  const naBase = parada?.tipo === "BASE_RETORNO";

  // Direção do caminhão: a do GPS quando existe; senão, a do deslocamento.
  if (ponto && anterior.current && distanciaM(anterior.current, ponto) > 5) {
    direcaoCalculada.current = rumo(anterior.current, ponto);
  }
  const direcao = posicao?.direcao_graus ?? direcaoCalculada.current;

  // Efeitos por leitura do GPS: guarda o segmento, detecta desvio.
  useEffect(() => {
    if (!ponto) return;
    anterior.current = ponto;
    if (!projecao) return;
    dica.current = projecao.segmento;

    const confiavel = (posicao.precisao_m ?? 0) < 60;
    if (confiavel && projecao.desvioM > DESVIO_M) leiturasFora.current += 1;
    else leiturasFora.current = 0;

    if (
      leiturasFora.current >= LEITURAS_PARA_DESVIO &&
      Date.now() - pedidoEm.current > RECALCULO_MIN_MS &&
      !calculando
    ) {
      if (voz) falar("Recalculando a rota");
      buscar(ponto);
    }
    // A cada leitura nova do GPS, e só por ela.
  }, [posicao]);

  // Voz: anuncia a manobra longe e de novo perto, uma vez cada.
  useEffect(() => {
    if (!voz || !nav) return;
    const falarUmaVez = (chave, texto) => {
      if (anunciado.current.has(chave)) return;
      anunciado.current.add(chave);
      falar(texto);
    };
    if (!anunciado.current.has("inicio") && nav.manobras?.[0]) {
      anunciado.current.add("inicio");
      const primeira = proxima ? fraseFalada(proxima.distanciaM, proxima.manobra.instrucao) : "";
      falar([nav.manobras[0].instrucao, primeira].filter(Boolean).join(". "));
      return;
    }
    if (chegou) {
      falarUmaVez("chegada", naBase ? "Você chegou à base" : "Você chegou ao destino");
      return;
    }
    if (!proxima) return;
    const { indice, distanciaM: d, manobra } = proxima;
    if (d <= AVISO_PERTO_M) falarUmaVez(`${indice}-perto`, manobra.instrucao);
    else if (d <= AVISO_LONGE_M) falarUmaVez(`${indice}-longe`, fraseFalada(d, manobra.instrucao));
  }, [voz, nav, proxima, chegou, naBase]);

  function alternarVoz() {
    const novo = !voz;
    setVoz(novo);
    if (!novo && "speechSynthesis" in window) window.speechSynthesis.cancel();
    try {
      localStorage.setItem(CHAVE_VOZ, novo ? "ligada" : "desligada");
    } catch {
      // preferência só desta sessão
    }
  }

  const Icone = chegou ? Flag : iconeDaManobra(proxima?.manobra);
  const linha = preparada?.pontos ?? (destino && ponto ? [ponto, destino] : []);
  const percorrida = projecao ? linha.slice(0, projecao.segmento + 1) : [];
  const falta = projecao ? [ponto, ...linha.slice(projecao.segmento + 1)] : linha;

  // ------------------------------------------------------------------ tela
  let cabecalho;
  if (!ponto) {
    cabecalho = <EstadoGps estado={rastreio.estado} />;
  } else if (!nav && (calculando || !erro)) {
    cabecalho = (
      <div className="nav__manobra nav__manobra--neutra">
        <Spinner tamanho={22} />
        <p className="nav__instrucao">Calculando a rota...</p>
      </div>
    );
  } else if (nav?.concluida) {
    cabecalho = (
      <div className="nav__manobra">
        <Flag size={40} strokeWidth={2.2} aria-hidden="true" />
        <p className="nav__instrucao">Nenhuma parada pendente.</p>
      </div>
    );
  } else {
    cabecalho = (
      <div className="nav__manobra" aria-live="polite">
        <Icone size={44} strokeWidth={2.4} aria-hidden="true" className="nav__icone" />
        <div className="nav__texto">
          {chegou ? (
            <p className="nav__instrucao">
              {naBase ? "Você chegou à base" : "Você chegou"}
            </p>
          ) : proxima ? (
            <>
              <p className="nav__distancia numero">{formatarDistancia(proxima.distanciaM)}</p>
              <p className="nav__instrucao">{proxima.manobra.instrucao}</p>
            </>
          ) : (
            <p className="nav__instrucao">
              {nav?.estimada ? "Siga em direção ao destino" : "Siga pela rota"}
            </p>
          )}
          {!chegou && proxima?.seguinte && proxima.seguinte.tipo !== "arrive" && (
            <p className="nav__depois">Depois: {proxima.seguinte.instrucao}</p>
          )}
        </div>
        {calculando && <Spinner tamanho={16} />}
      </div>
    );
  }

  return (
    <div className="nav" role="dialog" aria-label="Navegação">
      {cabecalho}

      <div className="nav__mapa">
        <MapPanel tema={tema} altura="100%" centro={ponto ?? undefined} zoom={17} permitirSatelite>
          {percorrida.length > 1 && (
            <Polyline
              positions={percorrida}
              pathOptions={{ color: "#8a93a6", weight: 6, opacity: 0.5 }}
            />
          )}
          {falta.length > 1 && (
            <Polyline
              positions={falta}
              pathOptions={{
                color: "#4f7cff",
                weight: 7,
                opacity: 0.95,
                dashArray: nav?.estimada ? "8 10" : undefined,
                lineCap: "round",
                lineJoin: "round",
              }}
            />
          )}
          {destino && <Marker position={destino} icon={iconeDestino} />}
          {ponto && (
            <Marker position={ponto} icon={iconeVeiculo(direcao)} zIndexOffset={1000} />
          )}
          <Seguir posicao={ponto} ativo={seguir} aoSoltar={() => setSeguir(false)} />
        </MapPanel>

        {!seguir && ponto && (
          <button type="button" className="nav__centralizar" onClick={() => setSeguir(true)}>
            <LocateFixed size={18} strokeWidth={2.2} aria-hidden="true" />
            Centralizar
          </button>
        )}
      </div>

      <div className="nav__rodape">
        {erro && <p className="nav__alerta">{erro}</p>}
        {nav?.aviso && <p className="nav__alerta">{nav.aviso}</p>}
        {tela && !tela.suportado && (
          <p className="nav__alerta">
            Este navegador não mantém a tela acesa sozinho. Com a tela apagada o GPS para.
          </p>
        )}

        {parada && (
          <div className="nav__destino">
            <MapPin size={16} strokeWidth={2.2} aria-hidden="true" />
            <div>
              <strong>{naBase ? "Base" : `${parada.sequencia}. ${parada.rotulo ?? "Entrega"}`}</strong>
              {parada.endereco && <span>{parada.endereco}</span>}
            </div>
          </div>
        )}

        {!chegou && nav && !nav.concluida && (
          <div className="nav__numeros">
            <span>
              <small>chegada</small>
              <strong className="numero">{chegada ? hora(chegada.toISOString()) : "—"}</strong>
            </span>
            <span>
              <small>falta</small>
              <strong className="numero">{formatarDistancia(restanteM)}</strong>
            </span>
            <span>
              <small>tempo</small>
              <strong className="numero">
                {restanteS != null ? `${Math.max(1, Math.round(restanteS / 60))} min` : "—"}
              </strong>
            </span>
            <Badge tom={nav.com_transito ? "sucesso" : "neutro"}>
              {nav.estimada ? "estimativa" : nav.com_transito ? "com trânsito" : "rua livre"}
            </Badge>
          </div>
        )}

        {chegou && parada && !naBase && parada.status !== "CHEGOU" && (
          <Button
            tamanho="lg"
            larguraTotal
            icone={MapPin}
            carregando={agindo}
            onClick={() => aoRegistrarChegada(parada.id)}
          >
            CHEGUEI — REGISTRAR
          </Button>
        )}

        <div className="nav__botoes">
          <Button
            variante="secundario"
            icone={voz ? Volume2 : VolumeX}
            onClick={alternarVoz}
            aria-pressed={voz}
          >
            {voz ? "Voz" : "Sem voz"}
          </Button>
          {ponto && (
            <Button variante="secundario" icone={Crosshair} onClick={() => buscar(ponto)}>
              Recalcular
            </Button>
          )}
          <Button variante="secundario" icone={X} onClick={aoSair}>
            Sair
          </Button>
        </div>
      </div>
    </div>
  );
}

/** O GPS ainda não entregou posição: diz por quê, e o que fazer. */
export function EstadoGps({ estado }) {
  const mensagens = {
    inseguro: [
      "O GPS está bloqueado nesta conexão.",
      "O navegador só libera a localização em HTTPS. Abra o sistema pelo endereço seguro.",
    ],
    negado: [
      "A localização foi negada.",
      "Libere a localização para este site nas configurações do navegador.",
    ],
    indisponivel: ["Este aparelho não informa localização.", ""],
    aguardando: ["Procurando sinal de GPS...", "Em área aberta costuma levar poucos segundos."],
    desligado: ["Inicie a rota para navegar.", ""],
  };
  const [titulo, detalhe] = mensagens[estado] ?? mensagens.aguardando;
  return (
    <div className="nav__manobra nav__manobra--neutra">
      {estado === "aguardando" ? (
        <Spinner tamanho={22} />
      ) : (
        <Crosshair size={32} strokeWidth={2} aria-hidden="true" />
      )}
      <div className="nav__texto">
        <p className="nav__instrucao">{titulo}</p>
        {detalhe && <p className="nav__depois">{detalhe}</p>}
      </div>
    </div>
  );
}
