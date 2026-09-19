import { CalendarDays, MapPinned, Route } from "lucide-react";

import { Card, EmptyState } from "../../components/ui";
import { useAuth } from "../../hooks/useAuth";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import "./driver.css";

/**
 * Tela inicial do motorista.
 *
 * Ainda não há rota para executar: entregas entram na Fase 3, o planejamento
 * na Fase 7 e a operação no celular na Fase 9. Até lá a tela diz o que falta,
 * em vez de exibir uma rota de mentira — o motorista é quem menos pode ser
 * induzido a confiar num dado inventado.
 */
export function DriverHome() {
  useDocumentTitle("Minha rota");
  const { usuario } = useAuth();

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
        <p className="mot-cab__texto">Seu acesso está ativo.</p>
      </header>

      <Card>
        <EmptyState icone={Route} titulo="Nenhuma rota para hoje" compacto>
          <p>
            Quando o administrador montar e confirmar a rota do dia, ela aparece
            aqui com o mapa, a próxima parada e os botões de entrega.
          </p>
        </EmptyState>
      </Card>

      <Card titulo="Como vai funcionar">
        <ol className="mot-passos">
          <li className="mot-passo">
            <span className="mot-passo__numero numero">1</span>
            <div>
              <strong>Iniciar rota</strong>
              <p>Você confirma a saída e a operação passa a acompanhar em tempo real.</p>
            </div>
          </li>
          <li className="mot-passo">
            <span className="mot-passo__numero numero">2</span>
            <div>
              <strong>Cheguei</strong>
              <p>Ao estacionar, um toque registra a chegada com o horário.</p>
            </div>
          </li>
          <li className="mot-passo">
            <span className="mot-passo__numero numero">3</span>
            <div>
              <strong>Entregue ou não entregue</strong>
              <p>
                Cada entrega da parada é resolvida por você. Se não der certo,
                escolhe o motivo e segue.
              </p>
            </div>
          </li>
        </ol>
      </Card>

      <p className="mot-rodape">
        <MapPinned size={13} strokeWidth={2} aria-hidden="true" />
        Operação em Campo Grande, MS
      </p>
    </>
  );
}
