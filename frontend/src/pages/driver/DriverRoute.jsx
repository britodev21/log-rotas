import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Check,
  CheckCircle2,
  Flag,
  MapPin,
  Navigation,
  Play,
  X,
} from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { motorista as api } from "../../api/operacao";
import {
  AjustarLimites,
  MapPanel,
  MarcadorBase,
  ParadasDaRota,
  TrajetoRota,
  corDaRota,
} from "../../components/map";
import {
  Alert,
  Badge,
  Button,
  Card,
  ErrorState,
  Modal,
  SelectField,
  SkeletonText,
  TextareaField,
} from "../../components/ui";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useTheme } from "../../hooks/useTheme";
import { useToast } from "../../hooks/useToast";
import { MOTIVOS_INSUCESSO, hora } from "../../utils/formato";
import "./driver.css";

const RESOLVIDOS = ["ENTREGUE", "NAO_ENTREGUE", "CANCELADA"];

/**
 * Pega a posição do aparelho, se der.
 *
 * Nunca rejeita: a coordenada é um bônus para o registro, não um requisito.
 * O navegador só libera geolocalização em contexto seguro (HTTPS), e nem
 * sempre há sinal — travar o motorista na calçada por causa disso seria
 * trocar a operação por um detalhe.
 */
function posicaoAtual() {
  return new Promise((resolver) => {
    if (!navigator.geolocation) return resolver({});
    navigator.geolocation.getCurrentPosition(
      (p) => resolver({ latitude: p.coords.latitude, longitude: p.coords.longitude }),
      () => resolver({}),
      { timeout: 5000, maximumAge: 30000 },
    );
  });
}

export function DriverRoute() {
  const { id } = useParams();
  const navegar = useNavigate();
  const toast = useToast();
  const { tema } = useTheme();

  const [rota, setRota] = useState(null);
  const [erro, setErro] = useState("");
  const [agindo, setAgindo] = useState(false);
  const [insucesso, setInsucesso] = useState(null);
  const [finalizacaoAberta, setFinalizacaoAberta] = useState(false);

  useDocumentTitle(rota ? `Rota ${rota.id}` : "Minha rota");

  const carregar = useCallback(async () => {
    setErro("");
    try {
      setRota(await api.rota(id));
    } catch (e) {
      console.error("Falha ao carregar a rota", e);
      setErro(mensagemDeErro(e, "Não foi possível carregar a rota."));
    }
  }, [id]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  async function executar(acao, mensagemOk) {
    setAgindo(true);
    try {
      await acao();
      if (mensagemOk) toast.sucesso(mensagemOk);
      await carregar();
    } catch (e) {
      console.error("Falha na ação do motorista", e);
      toast.erro("Não deu certo", mensagemDeErro(e));
    } finally {
      setAgindo(false);
    }
  }

  if (erro) {
    return (
      <Card>
        <ErrorState mensagem={erro} aoTentarNovamente={carregar} compacto />
        <div style={{ marginTop: "var(--e-4)" }}>
          <Button variante="secundario" icone={ArrowLeft} onClick={() => navegar("/motorista")}>
            Voltar
          </Button>
        </div>
      </Card>
    );
  }

  if (!rota) {
    return (
      <Card>
        <SkeletonText linhas={6} />
      </Card>
    );
  }

  const paradas = rota.stops.filter((p) => p.stop_type === "ENTREGA");
  const proxima = paradas.find((p) => p.status !== "CONCLUIDA");
  const progresso = rota.progresso ?? { total: 0, concluidas: 0, percentual: 0 };
  const iniciada = rota.status === "INICIADA";
  const finalizada = rota.status === "FINALIZADA";

  const pontos = [
    ...(rota.base?.latitude ? [[Number(rota.base.latitude), Number(rota.base.longitude)]] : []),
    ...paradas
      .filter((p) => p.latitude != null)
      .map((p) => [Number(p.latitude), Number(p.longitude)]),
  ];

  return (
    <>
      {/* ------------------------------------------------------ progresso */}
      <div className="mot-progresso">
        <div className="mot-progresso__texto">
          <span className="numero">{progresso.concluidas}</span> de{" "}
          <span className="numero">{progresso.total}</span> entregas
          {finalizada && <Badge tom="sucesso">rota finalizada</Badge>}
        </div>
        <div className="progresso">
          <div
            className="progresso__barra"
            style={{ width: `${progresso.percentual}%`, background: "var(--sucesso)" }}
          />
        </div>
      </div>

      {/* ----------------------------------------------------------- mapa */}
      <Card semPadding>
        <MapPanel tema={tema} altura={240}>
          {rota.base?.latitude && (
            <MarcadorBase
              base={{
                rotulo: rota.base.name,
                latitude: Number(rota.base.latitude),
                longitude: Number(rota.base.longitude),
              }}
            />
          )}
          <TrajetoRota rota={rota} cor={corDaRota(0)} />
          <ParadasDaRota rota={rota} cor={corDaRota(0)} />
          <AjustarLimites pontos={pontos} />
        </MapPanel>
      </Card>

      {/* ------------------------------------------------ ação principal */}
      {!iniciada && !finalizada && (
        <Card>
          <p className="mot-aviso">
            Sua rota está pronta. Inicie quando sair da base.
          </p>
          <Button
            tamanho="lg"
            larguraTotal
            icone={Play}
            carregando={agindo}
            onClick={() => executar(() => api.iniciar(rota.id), "Boa viagem!")}
          >
            INICIAR ROTA
          </Button>
        </Card>
      )}

      {iniciada && proxima && (
        <Card>
          <span className="rotulo-secao">Próxima parada</span>

          <h2 className="mot-parada__titulo">
            {proxima.sequence}. {proxima.label}
          </h2>
          {proxima.address && <p className="mot-parada__endereco">{proxima.address}</p>}

          {proxima.estimated_arrival && (
            <p className="mot-parada__previsao">
              Previsão de chegada: {hora(proxima.estimated_arrival)}
            </p>
          )}

          {proxima.items?.length > 1 && (
            <Alert tom="info">
              Esta parada tem {proxima.items.length} entregas. Registre uma por uma.
            </Alert>
          )}

          {/* Navegação externa é COMPLEMENTO do mapa interno, não
              substituto: o sistema continua sendo o lugar onde a operação
              acontece. */}
          {proxima.latitude && (
            <a
              className="mot-navegar"
              href={`https://www.google.com/maps/dir/?api=1&destination=${proxima.latitude},${proxima.longitude}`}
              target="_blank"
              rel="noreferrer"
            >
              <Navigation size={15} strokeWidth={2} aria-hidden="true" />
              Abrir navegação
            </a>
          )}

          <div className="mot-acoes">
            {proxima.status !== "CHEGOU" ? (
              <Button
                tamanho="lg"
                larguraTotal
                icone={MapPin}
                carregando={agindo}
                onClick={() =>
                  executar(async () => {
                    const posicao = await posicaoAtual();
                    await api.cheguei(proxima.id, posicao);
                  }, "Chegada registrada")
                }
              >
                CHEGUEI
              </Button>
            ) : (
              <p className="mot-aviso">
                Chegada registrada às {hora(proxima.arrived_at)}. Resolva cada
                entrega abaixo.
              </p>
            )}

            <ul className="mot-entregas">
              {proxima.items.map((item) => {
                const resolvido = RESOLVIDOS.includes(item.status);
                return (
                  <li className="mot-entrega" key={item.id}>
                    <div className="mot-entrega__info">
                      <span className="mot-entrega__nome">
                        Entrega #{item.delivery_id}
                      </span>
                      {resolvido && (
                        <Badge
                          tom={item.status === "ENTREGUE" ? "sucesso" : "perigo"}
                          ponto
                        >
                          {item.status === "ENTREGUE" ? "entregue" : "não entregue"}
                        </Badge>
                      )}
                    </div>

                    {!resolvido && (
                      <div className="mot-entrega__botoes">
                        <Button
                          tamanho="lg"
                          icone={Check}
                          carregando={agindo}
                          onClick={() =>
                            executar(async () => {
                              const posicao = await posicaoAtual();
                              await api.entregue(item.id, posicao);
                            }, "Entrega registrada")
                          }
                        >
                          ENTREGUE
                        </Button>
                        <Button
                          tamanho="lg"
                          variante="secundario"
                          icone={X}
                          onClick={() => setInsucesso(item)}
                        >
                          NÃO ENTREGUE
                        </Button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        </Card>
      )}

      {iniciada && !proxima && (
        <Card>
          <div className="mot-concluido">
            <CheckCircle2 size={36} strokeWidth={1.8} aria-hidden="true" />
            <h2>Todas as paradas foram resolvidas</h2>
            <p>Finalize a rota quando voltar para a base.</p>
          </div>
          <Button
            tamanho="lg"
            larguraTotal
            icone={Flag}
            onClick={() => setFinalizacaoAberta(true)}
          >
            FINALIZAR ROTA
          </Button>
        </Card>
      )}

      {/* --------------------------------------------- lista das paradas */}
      <Card titulo="Todas as paradas">
        <ol className="mot-lista">
          {paradas.map((parada) => {
            const concluida = parada.status === "CONCLUIDA";
            const atual = proxima?.id === parada.id;
            return (
              <li
                className={`mot-lista__item ${concluida ? "mot-lista__item--ok" : ""} ${
                  atual ? "mot-lista__item--atual" : ""
                }`}
                key={parada.id}
              >
                <span className="mot-lista__ordem numero">
                  {concluida ? <Check size={12} strokeWidth={3} /> : parada.sequence}
                </span>
                <span className="mot-lista__texto">
                  <strong>{parada.label}</strong>
                  {parada.address && <span>{parada.address}</span>}
                </span>
                {parada.items.length > 1 && (
                  <Badge tom="neutro">{parada.items.length}</Badge>
                )}
              </li>
            );
          })}
        </ol>
      </Card>

      {iniciada && proxima && (
        <Button
          variante="secundario"
          larguraTotal
          icone={Flag}
          onClick={() => setFinalizacaoAberta(true)}
        >
          Finalizar rota agora
        </Button>
      )}

      <ModalInsucesso
        item={insucesso}
        onFechar={() => setInsucesso(null)}
        onRegistrado={carregar}
      />

      <Modal
        aberto={finalizacaoAberta}
        titulo="Finalizar rota"
        onFechar={() => setFinalizacaoAberta(false)}
        tamanho="sm"
      >
        <div className="pilha">
          {progresso.restantes > 0 ? (
            <Alert tom="atencao" titulo={`${progresso.restantes} entrega(s) sem registro`}>
              Elas serão marcadas como <strong>não entregues</strong> e voltam
              para o planejamento. O sistema não dá por entregue o que você não
              registrou.
            </Alert>
          ) : (
            <p>Todas as entregas foram registradas. Bom trabalho.</p>
          )}

          <div className="acoes-direita">
            <Button variante="secundario" onClick={() => setFinalizacaoAberta(false)}>
              Voltar
            </Button>
            <Button
              icone={Flag}
              carregando={agindo}
              onClick={async () => {
                await executar(() => api.finalizar(rota.id), "Rota finalizada");
                setFinalizacaoAberta(false);
              }}
            >
              Finalizar
            </Button>
          </div>
        </div>
      </Modal>
    </>
  );
}

function ModalInsucesso({ item, onFechar, onRegistrado }) {
  const toast = useToast();
  const [motivo, setMotivo] = useState("");
  const [observacao, setObservacao] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (item) {
      setMotivo("");
      setObservacao("");
    }
  }, [item]);

  const exigeTexto = motivo === "OUTRO";

  async function enviar(evento) {
    evento.preventDefault();
    setEnviando(true);
    try {
      const posicao = await posicaoAtual();
      await api.naoEntregue(item.id, { motivo, observacao: observacao || null, ...posicao });
      toast.sucesso("Registrado", "A entrega volta para o planejamento.");
      onFechar();
      onRegistrado();
    } catch (e) {
      console.error("Falha ao registrar insucesso", e);
      toast.erro("Não deu certo", mensagemDeErro(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Modal
      aberto={Boolean(item)}
      titulo="Entrega não realizada"
      descricao="O motivo fica registrado com hora e local."
      onFechar={onFechar}
      tamanho="sm"
    >
      <form className="form-modal" onSubmit={enviar} noValidate>
        <SelectField
          label="O que aconteceu?"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          required
          obrigatorio
        >
          <option value="">Selecione</option>
          {MOTIVOS_INSUCESSO.map((m) => (
            <option value={m.valor} key={m.valor}>
              {m.rotulo}
            </option>
          ))}
        </SelectField>

        <TextareaField
          label={exigeTexto ? "Descreva o que houve" : "Observação (opcional)"}
          value={observacao}
          onChange={(e) => setObservacao(e.target.value)}
          required={exigeTexto}
          obrigatorio={exigeTexto}
        />

        <div className="acoes-direita">
          <Button variante="secundario" onClick={onFechar}>
            Cancelar
          </Button>
          <Button
            type="submit"
            variante="perigo"
            carregando={enviando}
            disabled={!motivo || (exigeTexto && !observacao)}
          >
            Registrar
          </Button>
        </div>
      </form>
    </Modal>
  );
}
