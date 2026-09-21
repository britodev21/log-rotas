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
 * Existe porque digitar endereço por extenso é a pior entrada possível para
 * geocodificação — "Av. Calógeras 1500" tem dezenas de grafias, e o
 * resultado é um pino no lugar errado ou nenhum resultado.
 *
 * O fluxo é o contrário: o CEP traz logradouro, bairro, cidade e UF já
 * normalizados dos Correios; a pessoa digita o número; e **o mapa se move
 * sozinho** até o ponto, sem nenhum botão no meio. Achou, mostrou.
 *
 * O único clique que sobra é o de correção: arrastar o pino quando o
 * endereço cai alguns metros fora — o que acontece em loteamento novo.
 *
 * Devolve ao formulário pai: endereço montado, CEP e coordenada.
 */

/** Espera antes de consultar o provedor.
 *
 *  Não é enfeite: o Nominatim permite UMA requisição por segundo, e buscar
 *  a cada tecla digitada queimaria o limite e bloquearia o IP. Novecentos
 *  milissegundos depois da última tecla dá a sensação de automático sem
 *  passar do que o provedor aceita. */
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

export function CampoEndereco({ valor, aoMudar, alturaMapa = 240 }) {
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
  const [ajustadoAMao, setAjustadoAMao] = useState(false);

  const [pino, setPino] = useState(
    valor?.latitude != null ? [Number(valor.latitude), Number(valor.longitude)] : null,
  );

  const aoMudarRef = useRef(aoMudar);
  aoMudarRef.current = aoMudar;

  // Guarda o último endereço já localizado. Sem isto, reabrir o formulário
  // de um registro que já tem pino dispararia uma busca desnecessária e
  // poderia mover um ponto que alguém ajustou à mão.
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
    });
  }, [enderecoFinal, cep, pino]);

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
    } catch (e) {
      console.error("Falha ao consultar CEP", e);
      setEnderecoCep(null);
      setErroCep(mensagemDeErro(e, "CEP não encontrado."));
    } finally {
      setBuscandoCep(false);
    }
  }, []);

  // Assim que o CEP fica completo, consulta. Fazer a pessoa clicar num botão
  // depois de digitar oito dígitos é atrito sem motivo.
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
      setAjustadoAMao(false);

      if (resultado.candidatos.length > 1) {
        // Mais de um lugar possível: o mapa já vai para o primeiro, mas a
        // lista fica visível. Quem escolhe é a pessoa — o sistema não
        // decide no escuro.
        setCandidatos(resultado.candidatos);
      } else if (primeiro.precision === "RUA") {
        setAvisoMapa(
          "Encontramos a rua, mas não o número exato. Confira o pino e ajuste se precisar.",
        );
      }
    } catch (e) {
      console.error("Falha ao localizar endereço", e);
      setAvisoMapa(mensagemDeErro(e, "Não foi possível consultar o mapa agora."));
    } finally {
      setLocalizando(false);
    }
  }, []);

  /**
   * Localização automática.
   *
   * Roda sempre que o endereço muda e fica completo o bastante. É o que faz
   * a tela se comportar como um mapa de verdade: terminou de digitar, o
   * ponto aparece.
   *
   * O ponto ajustado à mão é descartado quando o ENDEREÇO muda — o pino
   * antigo apontaria para outro lugar. Enquanto o endereço não muda, o
   * ajuste manual é preservado.
   */
  useEffect(() => {
    const texto = enderecoFinal?.trim() ?? "";
    if (texto.length < MINIMO_PARA_BUSCAR) return;
    if (texto === jaLocalizado.current) return;

    const id = setTimeout(() => localizar(texto), ESPERA_MS);
    return () => clearTimeout(id);
  }, [enderecoFinal, localizar]);

  const semPino = !pino;
  const estaProcurando = buscandoCep || localizando;

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
            <span>{buscandoCep ? "Consultando CEP..." : "Localizando no mapa..."}</span>
          </>
        ) : enderecoFinal ? (
          <>
            <MapPin size={13} strokeWidth={2} aria-hidden="true" />
            <span className="endereco__texto">{enderecoFinal}</span>
            {pino && (
              <Badge tom={ajustadoAMao ? "info" : "sucesso"} ponto>
                {ajustadoAMao ? "ajustado à mão" : "localizado"}
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
              onClick={() => {
                setPino([c.latitude, c.longitude]);
                setAjustadoAMao(false);
              }}
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
          zoom={pino ? 17 : 12}
        >
          <CliqueNoMapa
            aoClicar={(p) => {
              setPino(p);
              setAjustadoAMao(true);
            }}
          />
          {pino && (
            <Marker
              position={pino}
              draggable
              eventHandlers={{
                dragend: (e) => {
                  const { lat, lng } = e.target.getLatLng();
                  setPino([lat, lng]);
                  setAjustadoAMao(true);
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

      <div className="endereco__rodape">
        <span className="texto-3">
          {pino
            ? "Arraste o pino se precisar corrigir. O ponto marcado à mão não é sobrescrito depois."
            : "Sem ponto no mapa a entrega não entra no planejamento."}
        </span>
        {enderecoFinal && (
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
