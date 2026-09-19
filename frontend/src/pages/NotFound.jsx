import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

import { Button, Logo } from "../components/ui";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import "./auth.css";

export function NotFound() {
  useDocumentTitle("Pagina nao encontrada");

  return (
    <main className="erro-pagina">
      <div>
        <Logo tamanho={32} comTexto={false} />
        <p className="erro-pagina__codigo">404</p>
        <h1 className="erro-pagina__titulo">Esta pagina nao existe</h1>
        <p className="erro-pagina__texto">
          O endereco digitado nao corresponde a nenhuma tela do Log Rotas.
        </p>
        <div className="erro-pagina__acao">
          <Link to="/">
            <Button variante="secundario" icone={ArrowLeft}>
              Voltar ao inicio
            </Button>
          </Link>
        </div>
      </div>
    </main>
  );
}
