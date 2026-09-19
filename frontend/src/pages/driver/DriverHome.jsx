import { Alert, Card, EmptyState } from "../../components/ui";
import { useAuth } from "../../hooks/useAuth";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";

/**
 * Tela inicial do motorista.
 *
 * Ainda sem rota para executar: entregas e rotas entram nas Fases 3 e 7, e a
 * operacao no celular na Fase 9. Ate la esta tela diz o que falta, em vez de
 * exibir uma rota de mentira.
 */
export function DriverHome() {
  useDocumentTitle("Minha rota");
  const { usuario } = useAuth();

  return (
    <>
      <Alert tom="info" titulo={`Ola, ${usuario?.name?.split(" ")[0] ?? ""}`}>
        Seu acesso esta ativo.
      </Alert>

      <Card titulo="Minha rota de hoje">
        <EmptyState titulo="Nenhuma rota atribuida">
          <p>
            O planejamento de rotas ainda nao foi implantado. Quando o
            administrador montar e confirmar a rota do dia, ela aparece aqui com
            o mapa, a proxima parada e os botoes de entrega.
          </p>
        </EmptyState>
      </Card>
    </>
  );
}
