import { Outlet } from "react-router-dom";

import { Button } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import "./DriverLayout.css";

/**
 * Layout do motorista.
 *
 * Nao e o layout administrativo encolhido: e uma casca propria, sem menu
 * lateral, sem navegacao profunda e com area de toque grande. O motorista
 * esta de pe, com pressa, as vezes segurando caixa.
 */
export function DriverLayout() {
  const { usuario, sair } = useAuth();

  return (
    <div className="motorista">
      <header className="motorista__topo">
        <div>
          <span className="motorista__marca">Log Rotas</span>
          <span className="motorista__nome">{usuario?.name}</span>
        </div>
        <Button variante="secundario" onClick={sair}>
          Sair
        </Button>
      </header>

      <main className="motorista__conteudo">
        <Outlet />
      </main>
    </div>
  );
}
