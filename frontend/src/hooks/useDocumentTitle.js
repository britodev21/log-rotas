import { useEffect } from "react";

/** Mantem o titulo da aba coerente com a tela aberta. */
export function useDocumentTitle(titulo) {
  useEffect(() => {
    document.title = titulo ? `${titulo} · Log Rotas` : "Log Rotas";
  }, [titulo]);
}
