import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarDays, ChevronRight, MapPinned, Route } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { motorista as api } from "../../api/operacao";
import { Alert, Badge, Button, Card, EmptyState, ErrorState, SkeletonList } from "../../components/ui";
import { useAuth } from "../../hooks/useAuth";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { distancia, duracao } from "../../utils/formato";
import "./driver.css";

/**
 * Tela inicial do motorista.
 *
 * Se há uma rota em andamento, entra nela direto — o motorista não deveria
 * precisar escolher nada quando já está na rua. A lista só aparece quando há
 * decisão real a tomar (mais de uma rota, ou nenhuma começada).
 */
export function DriverHome() {
  useDocumentTitle("Minhas rotas");
  const { usuario } = useAuth();
  const navegar = useNavigate();

  const [rotas, setRotas] = useState(null);
  const [erro, setErro] = useState("");

  const carregar = useCallback(async () => {
    setErro("");
    try {
      const lista = await api.rotas();
      setRotas(lista);

      const emAndamento = lista.find((r) => r.status === "INICIADA");
      if (emAndamento) navegar(`/motorista/rota/${emAndamento.id}`, { replace: true });
    } catch (e) {
      console.error("Falha ao carregar rotas do motorista", e);
      setErro(mensagemDeErro(e, "Não foi possível carregar suas rotas."));
    }
  }, [navegar]);

  useEffect(() => {
    carregar();
  }, [carregar]);

  const primeiroNome = usuario?.name?.split(" ")[0] ?? "";
  const hoje = new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "2-digit",
  }).format(new Date());

  return (
    <>
      <header className="mot-cab">
        <span className="mot-cab__data">
          <CalendarDays size={14} strokeWidth={2} aria-hidden="true" />
          {hoje}
        </span>
        <h1 className="mot-cab__titulo">Olá, {primeiroNome}</h1>
      </header>

      {erro && (
        <Card>
          <ErrorState mensagem={erro} aoTentarNovamente={carregar} compacto />
        </Card>
      )}

      {!rotas && !erro && (
        <Card semPadding>
          <SkeletonList itens={2} />
        </Card>
      )}

      {rotas?.length === 0 && (
        <Card>
          <EmptyState icone={Route} titulo="Nenhuma rota para hoje" compacto>
            <p>
              Quando o administrador confirmar o planejamento, sua rota aparece
              aqui com o mapa e a lista de paradas.
            </p>
            <Button variante="secundario" onClick={carregar}>
              Atualizar
            </Button>
          </EmptyState>
        </Card>
      )}

      {rotas?.length > 0 && (
        <div className="pilha">
          {rotas.length > 1 && (
            <Alert tom="info">
              Você tem {rotas.length} rotas hoje. Só uma pode estar em andamento
              por vez.
            </Alert>
          )}

          {rotas.map((rota) => (
            <button
              type="button"
              className="cartao-rota"
              key={rota.id}
              onClick={() => navegar(`/motorista/rota/${rota.id}`)}
            >
              <div className="cartao-rota__topo">
                <span className="cartao-rota__titulo">
                  Rota {rota.sequence_in_day > 1 ? rota.sequence_in_day : ""} ·{" "}
                  {rota.vehicle?.name}
                </span>
                <Badge tom={rota.status === "FINALIZADA" ? "sucesso" : "info"} ponto>
                  {rota.status === "PLANEJADA" ? "aguardando" : "finalizada"}
                </Badge>
              </div>

              <div className="cartao-rota__numeros">
                <span>
                  <strong className="numero">{rota.progresso?.total ?? 0}</strong> entregas
                </span>
                <span>{distancia(rota.total_distance_m)}</span>
                <span>{duracao(rota.estimated_duration_s)}</span>
              </div>

              {rota.base && (
                <span className="cartao-rota__base">
                  <MapPinned size={13} strokeWidth={2} aria-hidden="true" />
                  Sai de {rota.base.name}
                </span>
              )}

              <ChevronRight
                size={20}
                strokeWidth={2}
                className="cartao-rota__seta"
                aria-hidden="true"
              />
            </button>
          ))}
        </div>
      )}
    </>
  );
}
