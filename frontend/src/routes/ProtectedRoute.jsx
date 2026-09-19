import { Navigate, useLocation } from "react-router-dom";

import { Splash } from "../components/ui/Splash";
import { useAuth } from "../hooks/useAuth";

/**
 * Porteiro das rotas.
 *
 * Esta checagem e de navegacao, nao de seguranca: quem garante a permissao e
 * o backend, que responde 403 de qualquer forma. Aqui so evitamos mostrar
 * uma tela que o usuario nao poderia usar.
 */
export function ProtectedRoute({ papel, children }) {
  const { autenticado, carregando, usuario } = useAuth();
  const local = useLocation();

  if (carregando) return <Splash />;

  if (!autenticado) {
    // `state` guarda para onde a pessoa queria ir; o login devolve ela la.
    return <Navigate to="/entrar" replace state={{ de: local.pathname }} />;
  }

  if (papel && usuario?.role !== papel) {
    return <Navigate to={usuario?.role === "ADMIN" ? "/admin" : "/motorista"} replace />;
  }

  return children;
}
