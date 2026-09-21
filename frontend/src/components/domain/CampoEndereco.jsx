import { useCallback, useEffect, useRef, useState } from "react";
import { Marker, useMapEvents } from "react-leaflet";
import { Check, Crosshair, MapPin, RotateCw } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { geocodificacao as api } from "../../api/operacao";
import { AjustarLimites, MapPanel } from "../map";
import { Alert, Badge, Button, InputField, Spinner } from "../ui";
import { useTheme } from "../../hooks/useTheme";
import "./CampoEndereco.css";

/**
 * Entrada de endereço brasileiro: CEP, número, complemento e o ponto no mapa.
 *
 * O fluxo tem três passos e o terceiro é obrigatório:
 *
 *   1. CEP    → rua, bairro, cidade e UF vêm dos Correios, e o mapa pula
 *               para a quadra do trecho antes de qualquer digitação.
 *   2. Número → o sistema procura sozinho e põe um pino provisório.
 *   3. Você   → arrasta o pino até o portão e confirma.
 *
 * O passo 3 existe porque o passo 2 não é confiável em Campo Grande, e isso
 * foi medido, não suposto: o OpenStreetMap tem número de porta em cerca de
 * 530 prédios da cidade. Em oito endereços reais das avenidas principais,
 * com CEP conferido, o provedor acertou o número em ZERO.
 *
 * Quer dizer que "Avenida Afonso Pena, 3000" vira um ponto qualquer de uma
 * avenida de 10 km. Mostrar isso com um selo verde de "localizado" — que é
 * o que esta tela fazia — é a forma mais eficiente de produzir entrega no
 * endereço errado: ninguém confere o que o sistema diz que já está certo.
 *
 * Por isso o pino automático aparece como PROVISÓRIO, e só o que uma pessoa
 * marcou conta como confirmado. O planejamento recusa o resto
 * (app/services/precisao.py no backend).
 *
 * Devolve ao pai: endereço montado, CEP, coordenada e `ponto_confirmado`.
 */

/** Espera antes de consultar o provedor.
 *
 *  Não é enfeite: o Nominatim permite UMA requisição por segundo, e buscar
 *  a cada tecla digitada queimaria o limite e bloquearia o IP. */
const ESPERA_MS = 900;

/** Abaixo disto o texto não identifica lugar nenhum e a busca só gastaria
 *  o limite do provedor. */
const MINIMO_PARA_BUSCAR = 10;

function CliqueNoMapa({ aoClicar }) {
  useMapEvents({ click: (e) => aoClicar([e.latlng.lat, e.latlng.lng]) });
  return null;
}

function formatarCep(valor) {
  const d = String(valor ?? "").replace(/\D/g, "").slice(0, 8);
  return d.length > 5 ? `${d.slice(0, 5)}-${d.slice(5)}` : d;
}

export function CampoEndereco({ valor, aoMudar, alturaMapa = 260 }) {
  const { tema } = useTheme();

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

  const [pino, setPino] = useState(
    valor?.latitude != null ? [Number(valor.latitude), Number(valor.longitude)] : null,
  );

  // Um registro já gravado como MANUAL chega confirmado: alguém marcou o
  // ponto um dia, e pedir de novo a cada edição transformaria a proteção
  // em burocracia.
  const [confirmado, setConfirmado] = useState(valor?.geocode_status === "MANUAL");

  const aoMudarRef = useRef(aoMudar);
  aoMudarRef.current = aoMudar;

  // Guarda o último endereço já procurado, para não repetir a consulta ao
  // reabrir um registro que já tem pino.
  const jaLocalizado = useRef(valor?.latitude != null ? (valor?.address ?? "") : null);

  const enderecoFinal = enderecoCep
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

  useEffect(() => {
    aoMudarRef.current({
      address: enderecoFinal || null,
      postal_code: cep.replace(/\D/g, "") || null,
      latitude: pino ? pino[0] : null,
      longitude: pino ? pino[1] : null,
      ponto_confirmado: confirmado,
    });
  }, [enderecoFinal, cep, pino, confirmado]);

  /** Marca o ponto como posto por uma pessoa. */
  const marcarAMao = useCallback((posicao) => {
    setPino(posicao);
    setConfirmado(true);
    setAvisoMapa("");
  }, []);

  // ------------------------------------------------------------------ CEP
  const buscarCep = useCallback(async (valorCep) => {
    const digitos = String(valorCep).replace(/\D/g, "");
    if (digitos.length !== 8) return;

    setBuscandoCep(true);
    setErroCep("");
    try {
      const dados = await api.cep(digitos);
      setEnderecoCep(dados);
      setManual("");

      // O CEP brasileiro é por TRECHO de rua, então esta coordenada já põe
      // o mapa na quadra certa — antes mesmo do número. Ela entra como
      // pino PROVISÓRIO: aponta a quadra, não a porta.
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
  }, [confirmado]);

  useEffect(() => {
    const digitos = cep.replace(/\D/g, "");
    if (digitos.length === 8 && digitos !== enderecoCep?.cep) {
      buscarCep(digitos);
    }
  }, [cep, enderecoCep, buscarCep]);

  // ---------------------------------------------------------------- Mapa
  const localizar = useCallback(async (texto) => {
    if (!texto || texto.trim().length < MINIMO_PARA_BUSCAR) return;

    setLocalizando(true);
    setAvisoMapa("");
    setCandidatos([]);
    try {
      const resultado = await api.buscar(texto.trim());
      jaLocalizado.current = texto;

      if (resultado.candidatos.length === 0) {
        setAvisoMapa(
          "Não encontramos este endereço. Clique no mapa para marcar o ponto.",
        );
        return;
      }

      const [primeiro] = resultado.candidatos;
      setPino([primeiro.latitude, primeiro.longitude]);
      setConfirmado(false);

      if (resultado.candidatos.length > 1) {
        // Mais de um lugar possível: o mapa vai para o primeiro, mas a
        // lista fica visível. Quem escolhe é a pessoa.
        setCandidatos(resultado.candidatos);
      }
    } catch (e) {
      console.error("Falha ao localizar endereço", e);
      setAvisoMapa(mensagemDeErro(e, "Não foi possível consultar o mapa agora."));
    } finally {
      setLocalizando(false);
    }
  }, []);

  /**
   * Localização automática: terminou de digitar, o pino provisório aparece.
   *
   * Não roda quando o ponto já foi confirmado à mão — mover um pino que
   * alguém conferiu seria desfazer trabalho humano com um palpite.
   */
  useEffect(() => {
    const texto = enderecoFinal?.trim() ?? "";
    if (texto.length < MINIMO_PARA_BUSCAR) return;
    if (texto === jaLocalizado.current) return;
    if (confirmado) return;

    const id = setTimeout(() => localizar(texto), ESPERA_MS);
    return () => clearTimeout(id);
  }, [enderecoFinal, localizar, confirmado]);

  const semPino = !pino;
  const estaProcurando = buscandoCep || localizando;
  const precisaConfirmar = Boolean(pino) && !confirmado;

  return (
    <div className="endereco">
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
              <Badge tom={confirmado ? "sucesso" : "atencao"} ponto>
                {confirmado ? "ponto confirmado" : "provisório"}
              </Badge>
            )}
          </>
        ) : (
          <span className="texto-3">
            Comece pelo CEP — rua, bairro e cidade vêm automaticamente.
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

      {/* O pedido de confirmação é o centro desta tela, não um rodapé.
          Diz o que fazer, por que, e o que acontece se não fizer. */}
      {precisaConfirmar && (
        <div className="endereco__confirmar">
          <Crosshair size={16} strokeWidth={2} aria-hidden="true" />
          <div>
            <strong>Este pino é provisório.</strong> Ele veio do CEP ou da busca, que
            em Campo Grande acertam a rua mas quase nunca o número.{" "}
            <strong>Arraste o pino até o portão</strong> — use o botão Satélite para
            enxergar o prédio. Sem confirmar, esta entrega não entra no planejamento.
          </div>
        </div>
      )}

      <div className="endereco__rodape">
        <span className="texto-3">
          {confirmado
            ? "Ponto confirmado. A busca automática não mexe mais nele."
            : "Clique no mapa ou arraste o pino para confirmar."}
        </span>
        {enderecoFinal && !confirmado && (
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
