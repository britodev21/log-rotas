import { useId, useState } from "react";

import "./Tooltip.css";

/**
 * Dica curta ao passar o mouse ou focar pelo teclado.
 *
 * Usada para nomear botao que so tem icone. Nunca para informacao
 * essencial: em tela de toque nao existe hover, e o conteudo ficaria
 * inalcancavel.
 */
export function Tooltip({ texto, lado = "cima", children }) {
  const [visivel, setVisivel] = useState(false);
  const id = useId();

  if (!texto) return children;

  return (
    <span
      className="dica-area"
      onMouseEnter={() => setVisivel(true)}
      onMouseLeave={() => setVisivel(false)}
      onFocus={() => setVisivel(true)}
      onBlur={() => setVisivel(false)}
    >
      <span aria-describedby={visivel ? id : undefined}>{children}</span>
      {visivel && (
        <span className={`dica dica--${lado}`} role="tooltip" id={id}>
          {texto}
        </span>
      )}
    </span>
  );
}
