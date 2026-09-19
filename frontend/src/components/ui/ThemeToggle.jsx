import { Moon, Sun } from "lucide-react";

import { useTheme } from "../../hooks/useTheme";
import { Button } from "./Button";
import { Tooltip } from "./Tooltip";

export function ThemeToggle({ tamanho = "sm" }) {
  const { escuro, alternar } = useTheme();

  return (
    <Tooltip texto={escuro ? "Tema claro" : "Tema escuro"} lado="baixo">
      <Button
        variante="sutil"
        tamanho={tamanho}
        icone={escuro ? Sun : Moon}
        onClick={alternar}
        aria-label={escuro ? "Mudar para tema claro" : "Mudar para tema escuro"}
      />
    </Tooltip>
  );
}
