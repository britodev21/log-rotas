import { useCallback, useEffect, useRef, useState } from "react";
import { Marker, useMapEvents } from "react-leaflet";
import { Check, CheckCircle2, Crosshair, MapPin, RotateCw } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { geocodificacao as api } from "../../api/operacao";
import { AjustarLimites, MapPanel } from "../map";
import { Alert, Badge, Button, InputField, Spinner } from "../ui";
import { useTheme } from "../../hooks/useTheme";
import { BuscaEndereco } from "./BuscaEndereco";
import "./CampoEndereco.css";

/**
 * Entrada de endereço e o ponto no mapa.
 *
 * Dois caminhos, e a ordem importa:
 *
 *   1. Busca do Google (quando configurada). A pessoa digita, escolhe um
 *      endereço que existe, e o ponto vem do cadastro do Google. Medido nos
 *      mesmos oito endereços de Campo Grande: número certo em oito de oito.
 *
 *   2. CEP + número, pelo geocodificador gratuito. Continua existindo para
 *      quando o Google não conhece o lugar (loteamento novo, chácara) ou não
 *      está configurado. Aqui o número certo saiu em ZERO de oito — o
 *      OpenStreetMap tem número de porta em cerca de 530 prédios da cidade —
 *      e por isso o pino vale como provisório.
 *
 * Em qualquer caminho, "achou o endereço" não é "o ponto é o portão". Só
 * dispensa conferência o que o Google provou ser o telhado (ROOFTOP), e
 * quem decide isso é o servidor, não esta tela. O resto pede um olhar no
 * satélite e um clique — o planejamento recusa pino não conferido.
 *
 * Devolve ao pai: endereço montado, CEP, coordenada, `ponto_confirmado` e
 * `google_place_id`.
 */

/** O Nominatim permite UMA requisição por segundo; buscar a cada tecla
 *  queimaria o limite e bloquearia o IP. */
const ESPERA_MS = 900;
const MINIMO_PARA_BUSCAR = 10;

// Uma consulta por carregamento de página basta: o que está ligado no
// servidor não muda enquanto a pessoa preenche formulários.
let recursosEmCache = null;
function carregarRecursos() {
  recursosEmCache ??= api.recursos().catch((e) => {
    console.error("Falha ao consultar recursos de geocodificação", e);
    recursosEmCache = null;
    return { autocomplete: false };
  });
  return recursosEmCache;
}

function CliqueNoMapa({ aoClicar }) {
  useMapEvents({ click: (e) => aoClicar([e.latlng.lat, e.latlng.lng]) });
  return null;
}

function formatarCep(valor) {
  const d = String(valor ?? "").replace(/\D/g, "").slice(0, 8);
  return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d;
}

const mesmoPonto = (a, b) =>
  Boolean(a && b) && Math.abs(a[0] - b[0]) < 1e-6 && Math.abs(a[1] - b[1]) < 1e-6;

function montarDoGoogle(lugar, complemento) {
  if (!lugar.logradouro) {
    // Estabelecimento ou lugar sem rua estruturada: o texto do Google é o
    // melhor que há.
    return [lugar.endereco_formatado, complemento || null].filter(Boolean).join(", ");
  }
  return [
    lugar.numero ? `${lugar.logradouro}, ${lugar.numero}` : lugar.logradouro,
    complemento || null,
    lugar.bairro,
    lugar.cidade && lugar.uf ? `${lugar.cidade} - ${lugar.uf}` : lugar.cidade,
    lugar.cep,
  ]
    .filter(Boolean)
    .join(", ");
}

export function CampoEndereco({ valor, aoMudar, alturaMapa = 260 }) {
  const { tema } = useTheme();

  const [recursos, setRecursos] = useState(null);
  const [modoCep, setModoCep] = useState(false);
  const [lugar, setLugar] = useState(null);

  const [cep, setCep] = useState(formatarCep(valor?.postal_code ?? ""));
  const [numero, setNumero] = useState("");
  const [complemento, setComplemento] = useState("");
  const [enderecoCep, setEnderecoCep] = useState(null);
  const [manual, setManual] = useState(valor?.address ?? "");

  const [buscandoCep, setBuscandoCep] = useState(false);
  const [localizando, setLocalizando] = useState(false);
  const [erroCep, setErroCep] = useState("");
  const [avisoMapa, setAvisoMapa] = useState("");
  const [candidatos, setCandidatos] = useState([]);

  const pontoInicial =
    valor?.latitude != null ? [Number(valor.latitude), Number(valor.longitude)] : null;
  const [pino, setPino] = useState(pontoInicial);

  // Registro já gravado como MANUAL chega confirmado; como EXATO, chega
  // provado. Pedir de novo a cada edição transformaria a proteção em
  // burocracia.
  const [confirmado, setConfirmado] = useState(valor?.geocode_status === "MANUAL");
  const exatoSalvo = useRef(
    valor?.geocode_precision === "EXATO" && valor?.geocode_status !== "MANUAL"
      ? pontoInicial
      : null,
  );

  const aoMudarRef = useRef(aoMudar);
  aoMudarRef.current = aoMudar;
  const jaLocalizado = useRef(valor?.latitude != null ? (valor?.address ?? "") : null);

  useEffect(() => {
    let vivo = true;
    carregarRecursos().then((r) => vivo && setRecursos(r));
    return () => {
      vivo = false;
    };
  }, []);

  const usarGoogle = Boolean(recursos?.autocomplete) && !modoCep;

  const enderecoFinal = lugar
    ? montarDoGoogle(lugar, complemento)
    : enderecoCep
      ? [
          enderecoCep.logradouro && numero
            ? `${enderecoCep.logradouro}, ${numero}`
            : enderecoCep.logradouro,
          complemento || null,
          enderecoCep.bairro,
          `${enderecoCep.cidade} - ${enderecoCep.uf}`,
          enderecoCep.cep_formatado,
        ]
          .filter(Boolean)
          .join(", ")
      : manual;

  const cepFinal = (lugar ? lugar.cep : cep)?.replace(/\D/g, "") || null;

  const exatoGoogle =
    Boolean(lugar) && lugar.precision === "EXATO" && mesmoPonto(pino, [lugar.latitude, lugar.longitude]);
  const exato = !confirmado && (exatoGoogle || mesmoPonto(pino, exatoSalvo.current));

  useEffect(() => {
    aoMudarRef.current({
      address: enderecoFinal || null,
      postal_code: cepFinal,
      latitude: pino ? pino[0] : null,
      longitude: pino ? pino[1] : null,
      ponto_confirmado: confirmado,
      // Só um identificador. Se o ponto é exato quem decide é o servidor,
      // conferindo no próprio cache — esta tela não consegue afirmar isso.
      google_place_id: lugar ? lugar.place_id : null,
    });
  }, [enderecoFinal, cepFinal, pino, confirmado, lugar]);

  /** Uma pessoa marcou ou conferiu o ponto. */
  const marcarAMao = useCallback((posicao) => {
    setPino(posicao);
    setConfirmado(true);
    setAvisoMapa("");
  }, []);

  // --------------------------------------------------------- Google
  const aoEscolherNoGoogle = useCallback((escolhido) => {
    setLugar(escolhido);
    setEnderecoCep(null);
    setCandidatos([]);
    setAvisoMapa("");
    setPino([escolhido.latitude, escolhido.longitude]);
    setConfirmado(false);
    exatoSalvo.current = null;
  }, []);

  const aoGoogleFalhar = useCallback((mensagem) => {
    // Chave recusada, cota, Google fora: o cadastro não pode parar por isso.
    setModoCep(true);
    setAvisoMapa(`${mensagem} Usando CEP por enquanto.`);
  }, []);

  // ------------------------------------------------------------ CEP
  const buscarCep = useCallback(
    async (valorCep) => {
      const digitos = String(valorCep).replace(/\D/g, "");
      if (digitos.length !== 8) return;

      setBuscandoCep(true);
      setErroCep("");
      try {
        const dados = await api.cep(digitos);
        setEnderecoCep(dados);
        setManual("");
        // O CEP é por trecho de rua: esta coordenada põe o mapa na quadra
        // certa antes do número. Entra como provisória — aponta a quadra,
        // não a porta.
        if (dados.latitude != null && !confirmado) {
          setPino([dados.latitude, dados.longitude]);
        }
      } catch (e) {
        console.error("Falha ao consultar CEP", e);
        setEnderecoCep(null);
        setErroCep(mensagemDeErro(e, "CEP não encontrado."));
      } finally {
        setBuscandoCep(false);
      }
    },
    [confirmado],
  );

  useEffect(() => {
    if (usarGoogle || lugar) return;
    const digitos = cep.replace(/\D/g, "");
    if (digitos.length === 8 && digitos !== enderecoCep?.cep) buscarCep(digitos);
  }, [cep, enderecoCep, buscarCep, usarGoogle, lugar]);

  const localizar = useCallback(async (texto) => {
    if (!texto || texto.trim().length < MINIMO_PARA_BUSCAR) return;

    setLocalizando(true);
    setAvisoMapa("");
    setCandidatos([]);
    try {
      const resultado = await api.buscar(texto.trim());
      jaLocalizado.current = texto;
      if (resultado.candidatos.length === 0) {
        setAvisoMapa("Não encontramos este endereço. Clique no mapa para marcar o ponto.");
        return;
      }
      const [primeiro] = resultado.candidatos;
      setPino([primeiro.latitude, primeiro.longitude]);
      setConfirmado(false);
      if (resultado.candidatos.length > 1) setCandidatos(resultado.candidatos);
    } catch (e) {
      console.error("Falha ao localizar endereço", e);
      setAvisoMapa(mensagemDeErro(e, "Não foi possível consultar o mapa agora."));
    } finally {
      setLocalizando(false);
    }
  }, []);

  // Localização automática do caminho por CEP. Não roda no caminho do
  // Google — lá o ponto já veio da escolha — nem sobre ponto conferido.
  useEffect(() => {
    if (usarGoogle || lugar || confirmado) return undefined;
    const texto = enderecoFinal?.trim() ?? "";
    if (texto.length < MINIMO_PARA_BUSCAR || texto === jaLocalizado.current) return undefined;
    const id = setTimeout(() => localizar(texto), ESPERA_MS);
    return () => clearTimeout(id);
  }, [enderecoFinal, localizar, confirmado, usarGoogle, lugar]);

  function trocarParaCep() {
    setModoCep(true);
    setLugar(null);
  }

  function voltarParaGoogle() {
    setModoCep(false);
    setEnderecoCep(null);
    setAvisoMapa("");
    setCandidatos([]);
  }

  const semPino = !pino;
  const estaProcurando = buscandoCep || localizando;
  const precisaConfirmar = Boolean(pino) && !confirmado && !exato;

  let motivoConfirmacao;
  if (lugar && lugar.tipo_ponto === "RANGE_INTERPOLATED") {
    motivoConfirmacao =
      "O Google achou o número, mas o ponto é estimado entre as casas da quadra.";
  } else if (lugar && !lugar.numero) {
    motivoConfirmacao =
      "Este resultado não tem número. Digite o número na busca ou marque o portão no mapa.";
  } else if (lugar) {
    motivoConfirmacao =
      "O Google achou o endereço, mas não garantiu que o ponto é o do prédio.";
  } else {
    motivoConfirmacao =
      "Ele veio do CEP ou da busca gratuita, que em Campo Grande acertam a rua mas quase nunca o número.";
  }

  if (recursos === null) {
    return (
      <div className="endereco endereco--carregando">
        <Spinner tamanho={14} />
        <span className="texto-3">Preparando a busca de endereço...</span>
      </div>
    );
  }

  return (
    <div className="endereco">
      {usarGoogle ? (
        <>
          <BuscaEndereco
            valorInicial={valor?.address ?? ""}
            aoEscolher={aoEscolherNoGoogle}
            aoFalhar={aoGoogleFalhar}
          />
          <div className="endereco__linha endereco__linha--google">
            <div className="endereco__complemento">
              <InputField
                label="Complemento"
                placeholder="Apto, bloco, fundos"
                value={complemento}
                onChange={(e) => setComplemento(e.target.value)}
              />
            </div>
            <button type="button" className="endereco__troca" onClick={trocarParaCep}>
              Não achou? Buscar pelo CEP
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="endereco__linha">
            <div className="endereco__cep">
              <InputField
                label="CEP"
                placeholder="79000-000"
                inputMode="numeric"
                value={cep}
                onChange={(e) => setCep(formatarCep(e.target.value))}
                erro={erroCep}
              />
            </div>
            <div className="endereco__numero">
              <InputField
                label="Número"
                inputMode="numeric"
                value={numero}
                onChange={(e) => setNumero(e.target.value)}
                disabled={!enderecoCep}
              />
            </div>
            <div className="endereco__complemento">
              <InputField
                label="Complemento"
                placeholder="Apto, bloco, fundos"
                value={complemento}
                onChange={(e) => setComplemento(e.target.value)}
                disabled={!enderecoCep}
              />
            </div>
          </div>

          {!enderecoCep && !buscandoCep && (
            <InputField
              label="Ou digite o endereço completo"
              placeholder="Rua, número, bairro, cidade"
              value={manual}
              onChange={(e) => setManual(e.target.value)}
              ajuda="Use quando não souber o CEP. O resultado costuma ser menos preciso."
            />
          )}

          {recursos?.autocomplete && (
            <button type="button" className="endereco__troca" onClick={voltarParaGoogle}>
              Voltar para a busca do Google
            </button>
          )}
        </>
      )}

      {/* Uma linha só, que troca de conteúdo conforme o estado. Empilhar
          avisos faria o formulário pular de altura a cada tecla. */}
      <div className="endereco__estado">
        {estaProcurando ? (
          <>
            <Spinner tamanho={13} />
            <span>{buscandoCep ? "Consultando CEP..." : "Procurando no mapa..."}</span>
          </>
        ) : enderecoFinal ? (
          <>
            <MapPin size={13} strokeWidth={2} aria-hidden="true" />
            <span className="endereco__texto">{enderecoFinal}</span>
            {pino && (
              <Badge tom={confirmado || exato ? "sucesso" : "atencao"} ponto>
                {confirmado ? "ponto confirmado" : exato ? "ponto exato" : "provisório"}
              </Badge>
            )}
          </>
        ) : (
          <span className="texto-3">
            {usarGoogle
              ? "Digite o endereço e escolha na lista — o ponto vem junto."
              : "Comece pelo CEP — rua, bairro e cidade vêm automaticamente."}
          </span>
        )}
      </div>

      {avisoMapa && <Alert tom="atencao">{avisoMapa}</Alert>}

      {candidatos.length > 1 && (
        <div className="endereco__candidatos">
          <p className="rotulo-secao">Encontramos mais de um lugar</p>
          {candidatos.map((c, i) => (
            <button
              type="button"
              key={i}
              className={`endereco__candidato ${
                pino && pino[0] === c.latitude ? "endereco__candidato--ativo" : ""
              }`}
              onClick={() => setPino([c.latitude, c.longitude])}
            >
              {pino && pino[0] === c.latitude && (
                <Check size={13} strokeWidth={3} aria-hidden="true" />
              )}
              <span>{c.display_name}</span>
            </button>
          ))}
        </div>
      )}

      <div className={`endereco__mapa ${semPino ? "endereco__mapa--vazio" : ""}`}>
        <MapPanel
          tema={tema}
          altura={alturaMapa}
          centro={pino ?? undefined}
          zoom={pino ? 18 : 12}
          permitirSatelite
        >
          <CliqueNoMapa aoClicar={marcarAMao} />
          {pino && (
            <Marker
              position={pino}
              draggable
              eventHandlers={{
                dragend: (e) => {
                  const { lat, lng } = e.target.getLatLng();
                  marcarAMao([lat, lng]);
                },
              }}
            />
          )}
          <AjustarLimites pontos={pino ? [pino] : []} ativo={Boolean(pino)} />
        </MapPanel>

        {semPino && !estaProcurando && (
          <div className="endereco__mapa-vazio">
            <Crosshair size={18} strokeWidth={1.8} aria-hidden="true" />
            <span>O ponto aparece aqui assim que o endereço for reconhecido</span>
          </div>
        )}
      </div>

      {/* O pedido de confirmação é o centro desta tela, não um rodapé. Diz o
          que aconteceu, o que fazer e o que acontece se não fizer. */}
      {precisaConfirmar && (
        <div className="endereco__confirmar">
          <Crosshair size={16} strokeWidth={2} aria-hidden="true" />
          <div className="endereco__confirmar-texto">
            <p>
              <strong>Confira o ponto.</strong> {motivoConfirmacao} Ligue o{" "}
              <strong>Satélite</strong>, veja se o pino está no portão e arraste se precisar.
              Sem conferir, esta entrega não entra no planejamento.
            </p>
            <Button
              variante="secundario"
              tamanho="sm"
              icone={CheckCircle2}
              onClick={() => marcarAMao(pino)}
            >
              Conferi — o ponto está no portão
            </Button>
          </div>
        </div>
      )}

      <div className="endereco__rodape">
        <span className="texto-3">
          {confirmado
            ? "Ponto conferido por você. A busca automática não mexe mais nele."
            : exato
              ? "O Google confirmou que este é o ponto do prédio. Arraste só se souber que o portão é outro."
              : "Clique no mapa ou arraste o pino para marcar o portão."}
        </span>
        {!usarGoogle && enderecoFinal && !confirmado && (
          <Button
            variante="texto"
            tamanho="sm"
            icone={RotateCw}
            onClick={() => localizar(enderecoFinal)}
            carregando={localizando}
          >
            Procurar de novo
          </Button>
        )}
      </div>
    </div>
  );
}
