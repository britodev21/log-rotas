import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Marker, useMapEvents } from "react-leaflet";
import { MapPin, MapPinned, Search, Wand2 } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { geocodificacao as api } from "../../api/operacao";
import { AjustarLimites, MapPanel } from "../../components/map";
import { GeocodeBadge } from "../../components/domain";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  InputField,
  PageHeader,
  SelectField,
  SkeletonList,
} from "../../components/ui";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useTheme } from "../../hooks/useTheme";
import { useToast } from "../../hooks/useToast";
import "./admin.css";

const CAMPO_GRANDE = [-20.4697, -54.6201];

/** Captura o clique no mapa para posicionar o pino. */
function CliqueNoMapa({ aoClicar }) {
  useMapEvents({ click: (evento) => aoClicar([evento.latlng.lat, evento.latlng.lng]) });
  return null;
}

/**
 * Fila de revisão de endereços.
 *
 * Existe porque geocodificação automática erra, e endereço errado vira rota
 * errada. Aqui o administrador vê o que não resolveu e **corrige o pino no
 * mapa** — uma vez, para sempre: a coordenada manual nunca é sobrescrita
 * pela geocodificação automática.
 *
 * Importa especialmente em Campo Grande, onde loteamento novo e chácara têm
 * cobertura irregular no OpenStreetMap.
 */
export function GeocodeQueue() {
  useDocumentTitle("Endereços");
  const toast = useToast();
  const { tema } = useTheme();

  const [itens, setItens] = useState(null);
  const [erro, setErro] = useState("");
  const [tipo, setTipo] = useState("");
  const [selecionado, setSelecionado] = useState(null);
  const [pino, setPino] = useState(null);
  // Onde o mapa vai. So o sistema o move; o clique e o arrasto da pessoa
  // mexem no pino e deixam o zoom como ela deixou.
  const [enquadrar, setEnquadrar] = useState(null);
  const apontar = useCallback((p) => {
    setPino(p);
    setEnquadrar(p);
  }, []);
  const [salvando, setSalvando] = useState(false);
  const [processando, setProcessando] = useState(false);
  const [busca, setBusca] = useState("");
  const [candidatos, setCandidatos] = useState([]);
  const [buscando, setBuscando] = useState(false);
  const ultimaBusca = useRef(null);

  const carregar = useCallback(async () => {
    setErro("");
    try {
      setItens(await api.pendentes(tipo ? { tipo } : {}));
    } catch (e) {
      console.error("Falha ao carregar a fila de endereços", e);
      setErro(mensagemDeErro(e, "Não foi possível carregar a fila."));
    }
  }, [tipo]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const buscarNoMapa = useCallback(
    async (texto) => {
      if (!texto || texto.trim().length < 3) return;
      setBuscando(true);
      setCandidatos([]);
      try {
        const resultado = await api.buscar(texto.trim());
        setCandidatos(resultado.candidatos);
        // Aponta o primeiro na hora. Devolver uma lista sem mexer no mapa
        // obrigaria a pessoa a um clique a mais só para ver onde caiu.
        if (resultado.candidatos.length > 0) {
          const c = resultado.candidatos[0];
          apontar([c.latitude, c.longitude]);
        } else {
          toast.atencao(
            "Nada encontrado",
            "Marque o ponto clicando direto no mapa.",
          );
        }
      } catch (e) {
        console.error("Falha ao buscar endereço", e);
        toast.erro("Não foi possível buscar", mensagemDeErro(e));
      } finally {
        setBuscando(false);
      }
    },
    [toast, apontar],
  );

  // Procura sozinho quando a digitacao para. A espera nao e enfeite: o
  // Nominatim permite UMA consulta por segundo, e buscar a cada tecla
  // queimaria o limite e bloquearia o IP.
  useEffect(() => {
    const texto = busca.trim();
    if (texto.length < 8) return;
    if (texto === ultimaBusca.current) return;

    const id = setTimeout(() => {
      ultimaBusca.current = texto;
      buscarNoMapa(texto);
    }, 900);
    return () => clearTimeout(id);
  }, [busca, buscarNoMapa]);

  function selecionar(item) {
    setSelecionado(item);
    setCandidatos([]);
    setBusca(item.address ?? "");

    if (item.latitude) {
      apontar([item.latitude, item.longitude]);
      return;
    }

    // Sem coordenada, o endereço vai para o campo de busca e o efeito
    // acima o localiza sozinho: o objetivo da tela é ver onde ele cai, e
    // esperar um clique para isso é atrito puro.
    setPino(null);
    ultimaBusca.current = null;
  }

  async function tentarGeocodificar(item) {
    setProcessando(true);
    try {
      const resultado = await api.umRegistro(item.tipo, item.id);
      if (resultado.status === "OK") {
        toast.sucesso("Endereço localizado", resultado.normalized_address ?? "");
      } else if (resultado.status === "AMBIGUO") {
        toast.atencao(
          "Vários endereços possíveis",
          "O sistema não escolhe sozinho. Marque o ponto certo no mapa.",
        );
      } else {
        toast.erro("Endereço não localizado", resultado.error ?? "");
      }
      await carregar();
      setSelecionado(null);
    } catch (e) {
      console.error("Falha ao geocodificar", e);
      toast.erro("Não foi possível consultar", mensagemDeErro(e));
    } finally {
      setProcessando(false);
    }
  }

  async function processarLote() {
    setProcessando(true);
    toast.info(
      "Processando endereços",
      "O provedor permite uma consulta por segundo, então isso leva um tempo.",
    );
    try {
      const alvo = tipo || "entrega";
      const resultado = await api.lote({ tipo: alvo, limite: 50 });
      toast.sucesso(
        "Lote processado",
        `${resultado.ok} localizado(s), ${resultado.ambiguo} ambíguo(s), ${resultado.falhou} sem resultado.`,
      );
      await carregar();
    } catch (e) {
      console.error("Falha no lote de geocodificação", e);
      toast.erro("Não foi possível processar", mensagemDeErro(e));
    } finally {
      setProcessando(false);
    }
  }

  async function salvarPino() {
    if (!pino || !selecionado) return;
    setSalvando(true);
    try {
      await api.definirCoordenada(selecionado.tipo, selecionado.id, pino[0], pino[1]);
      toast.sucesso(
        "Ponto marcado",
        "A geocodificação automática não vai mais sobrescrever este endereço.",
      );
      setSelecionado(null);
      setPino(null);
      await carregar();
    } catch (e) {
      console.error("Falha ao gravar coordenada", e);
      toast.erro("Não foi possível gravar", mensagemDeErro(e));
    } finally {
      setSalvando(false);
    }
  }

  const centro = useMemo(() => pino ?? CAMPO_GRANDE, [pino]);

  return (
    <>
      <PageHeader
        titulo="Endereços"
        descricao="O que ainda não tem ponto confirmado. Sem isso, a entrega não entra no planejamento."
        acoes={
          <Button icone={Wand2} onClick={processarLote} carregando={processando}>
            Geocodificar pendentes
          </Button>
        }
      />

      <Alert tom="info" titulo="Por que quase tudo cai aqui">
        Em Campo Grande o OpenStreetMap tem número de porta em cerca de{" "}
        <strong>530 prédios</strong>. Em oito endereços reais das avenidas
        principais, o provedor gratuito acertou o número em{" "}
        <strong>nenhum</strong> — ele acha a rua, não a casa. Um pino desses
        numa rota parece perfeito e manda o caminhão para um ponto qualquer
        da via.
        <br />
        Por isso o ponto automático vale como <strong>provisório</strong>. Use
        o botão <strong>Satélite</strong> para enxergar o prédio, marque o
        portão e grave: é uma vez por endereço, e o sistema não pergunta de
        novo.
      </Alert>

      <div className="fila-enderecos">
        <Card
          titulo="Pendências"
          descricao={itens ? `${itens.length} registro(s)` : undefined}
          acoes={
            <div style={{ width: 150 }}>
              <SelectField label="" value={tipo} onChange={(e) => setTipo(e.target.value)}>
                <option value="">Todos</option>
                <option value="entrega">Entregas</option>
                <option value="cliente">Clientes</option>
                <option value="base">Bases</option>
              </SelectField>
            </div>
          }
        >
          {!itens && !erro && <SkeletonList itens={4} />}

          {erro && <ErrorState mensagem={erro} aoTentarNovamente={carregar} compacto />}

          {itens?.length === 0 && (
            <EmptyState icone={MapPinned} titulo="Nenhuma pendência" compacto>
              <p>Todos os endereços cadastrados já têm coordenada confiável.</p>
            </EmptyState>
          )}

          {itens?.length > 0 && (
            <ul className="fila-lista">
              {itens.map((item) => (
                <li
                  key={`${item.tipo}-${item.id}`}
                  className={`fila-item ${
                    selecionado?.id === item.id && selecionado?.tipo === item.tipo
                      ? "fila-item--ativo"
                      : ""
                  }`}
                  onClick={() => selecionar(item)}
                >
                  <div className="fila-item__texto">
                    <span className="fila-item__titulo">
                      {item.titulo}
                      <Badge tom="neutro">{item.tipo}</Badge>
                    </span>
                    <span className="fila-item__endereco">
                      {item.address ?? "sem endereço cadastrado"}
                    </span>
                    {(item.motivo || item.geocode_error) && (
                      <span className="fila-item__erro">
                        {item.geocode_error || item.motivo}
                      </span>
                    )}
                  </div>
                  <GeocodeBadge
                    status={item.geocode_status}
                    semEndereco={!item.address}
                  />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card
          titulo={selecionado ? "Marcar o ponto" : "Selecione um endereço"}
          descricao={selecionado?.address ?? "Clique num registro à esquerda."}
          semPadding
        >
          <MapPanel
            tema={tema}
            centro={centro}
            zoom={pino ? 18 : 12}
            altura={400}
            permitirSatelite
          >
            <CliqueNoMapa aoClicar={setPino} />
            {pino && (
              <Marker
                position={pino}
                draggable
                eventHandlers={{
                  dragend: (evento) => {
                    const { lat, lng } = evento.target.getLatLng();
                    setPino([lat, lng]);
                  },
                }}
              />
            )}
            <AjustarLimites
              pontos={enquadrar ? [enquadrar] : []}
              ativo={Boolean(enquadrar)}
              zoomUnico={18}
            />
          </MapPanel>

          <div className="fila-busca">
            <div className="crescer">
              <InputField
                label="Buscar endereço no mapa"
                placeholder="Rua, número, bairro, cidade"
                ajuda="Procura sozinho ao parar de digitar."
                icone={Search}
                value={busca}
                onChange={(e) => setBusca(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    buscarNoMapa(busca);
                  }
                }}
              />
            </div>
            <Button
              variante="secundario"
              icone={Search}
              onClick={() => buscarNoMapa(busca)}
              carregando={buscando}
              disabled={busca.trim().length < 3}
              title="A busca acontece sozinha ao parar de digitar; use para repetir."
            >
              Buscar
            </Button>
          </div>

          {candidatos.length > 0 && (
            <ul className="fila-candidatos">
              {candidatos.map((c, i) => (
                <li key={i}>
                  <button
                    type="button"
                    className={`fila-candidato ${
                      pino && pino[0] === c.latitude ? "fila-candidato--ativo" : ""
                    }`}
                    onClick={() => apontar([c.latitude, c.longitude])}
                  >
                    <MapPin size={13} strokeWidth={2} aria-hidden="true" />
                    <span>{c.display_name}</span>
                    {c.precision && <Badge tom="neutro">{c.precision.toLowerCase()}</Badge>}
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div className="fila-acoes">
            {!selecionado ? (
              <p className="texto-3">
                Escolha um endereço na lista para conferir e corrigir a posição.
              </p>
            ) : (
              <>
                <p className="texto-3">
                  {pino
                    ? "Arraste o pino até o portão. Ligue o satélite para ver o prédio."
                    : "Clique no mapa onde fica este endereço."}
                </p>
                <div className="acoes-direita">
                  <Button
                    variante="secundario"
                    icone={Wand2}
                    onClick={() => tentarGeocodificar(selecionado)}
                    carregando={processando}
                    title="Grava automaticamente se o provedor tiver certeza."
                  >
                    Resolver automático
                  </Button>
                  <Button
                    icone={MapPin}
                    onClick={salvarPino}
                    disabled={!pino}
                    carregando={salvando}
                  >
                    Gravar este ponto
                  </Button>
                </div>
              </>
            )}
          </div>
        </Card>
      </div>
    </>
  );
}
