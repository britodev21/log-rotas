import { useContext } from "react";

import { ThemeContext } from "../contexts/ThemeContext";

export function useTheme() {
  const contexto = useContext(ThemeContext);
  if (!contexto) throw new Error("useTheme precisa estar dentro de <ThemeProvider>.");
  return contexto;
}
