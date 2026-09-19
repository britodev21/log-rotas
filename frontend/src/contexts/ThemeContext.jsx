/**
 * Tema claro / escuro.
 *
 * O tema e aplicado no <html> por um script inline em index.html, antes do
 * React montar, para a tela nao piscar clara antes de virar escura. Este
 * contexto apenas le o que ja esta la e permite trocar.
 */

import { createContext, useCallback, useEffect, useMemo, useState } from "react";

const CHAVE = "logrotas.tema";

export const ThemeContext = createContext(null);

function temaAtual() {
  if (typeof document === "undefined") return "claro";
  return document.documentElement.getAttribute("data-tema") || "claro";
}

export function ThemeProvider({ children }) {
  const [tema, setTema] = useState(temaAtual);

  const aplicar = useCallback((novo) => {
    document.documentElement.setAttribute("data-tema", novo);
    setTema(novo);
    try {
      localStorage.setItem(CHAVE, novo);
    } catch {
      /* armazenamento bloqueado: o tema vale so nesta aba */
    }
  }, []);

  const alternar = useCallback(
    () => aplicar(tema === "escuro" ? "claro" : "escuro"),
    [tema, aplicar],
  );

  // Acompanha a preferencia do sistema enquanto o usuario nao tiver
  // escolhido manualmente. Depois da escolha, ela manda.
  useEffect(() => {
    const consulta = window.matchMedia("(prefers-color-scheme: dark)");
    const aoMudar = (evento) => {
      try {
        if (localStorage.getItem(CHAVE)) return;
      } catch {
        /* sem armazenamento: segue a preferencia do sistema */
      }
      const novo = evento.matches ? "escuro" : "claro";
      document.documentElement.setAttribute("data-tema", novo);
      setTema(novo);
    };
    consulta.addEventListener("change", aoMudar);
    return () => consulta.removeEventListener("change", aoMudar);
  }, []);

  const valor = useMemo(
    () => ({ tema, escuro: tema === "escuro", alternar, aplicar }),
    [tema, alternar, aplicar],
  );

  return <ThemeContext.Provider value={valor}>{children}</ThemeContext.Provider>;
}
