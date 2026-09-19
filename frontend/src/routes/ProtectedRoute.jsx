import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../hooks/useAuth";

/**
 * Porteiro das rotas.
 *
 * Esta checagem e de navegacao, nao de seguranca: quem garante a permissao e
 * o backend. Aqui so evitamos mostrar uma tela que o usuario nao pode usar.
 */
export function ProtectedRoute({ papel, children }) {
  const { autenticado, carregando, usuario } = useAuth();
  const local = useLocation();

  if (carregando) {
    return <div className="carregando-tela">Carregando...</div>;
  }

  if (!autenticado) {
    // `state` preserva para onde a pessoa queria ir, e o login devolve ela la.
    return <Navigate to="/entrar" replace state={{ de: local.pathname }} />;
  }

  if (papel && usuario?.role !== papel) {
    return <Navigate to={usuario?.role === "ADMIN" ? "/admin" : "/motorista"} replace />;
  }

  return children;
}
