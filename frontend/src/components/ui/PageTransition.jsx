import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import "./PageTransition.css";

/**
 * Transicao entre telas.
 *
 * Um fade curto com deslocamento minimo. A funcao nao e decorativa: a
 * mudanca sinaliza que a tela trocou, em vez de o conteudo se teletransportar
 * e obrigar a pessoa a reler tudo para descobrir onde esta.
 *
 * Curto de proposito. Transicao longa e a maneira mais rapida de fazer um
 * sistema de trabalho parecer lento.
 */
export function PageTransition({ children }) {
  const { pathname } = useLocation();
  const [chave, setChave] = useState(pathname);

  useEffect(() => {
    setChave(pathname);
  }, [pathname]);

  return (
    <div className="transicao" key={chave}>
      {children}
    </div>
  );
}
