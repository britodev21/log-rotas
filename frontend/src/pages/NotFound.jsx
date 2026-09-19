import { Link } from "react-router-dom";

import { useDocumentTitle } from "../hooks/useDocumentTitle";
import "./auth.css";

export function NotFound() {
  useDocumentTitle("Pagina nao encontrada");

  return (
    <div className="entrada">
      <div className="entrada__caixa">
        <p className="entrada__marca">404</p>
        <p className="entrada__subtitulo">Esta pagina nao existe no Log Rotas.</p>
        <p className="entrada__rodape">
          <Link to="/">Voltar ao inicio</Link>
        </p>
      </div>
    </div>
  );
}
