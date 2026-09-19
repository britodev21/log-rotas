import { useEffect, useRef } from "react";

import "./Modal.css";

/** Caixa de dialogo modal, fechavel por Esc, pelo X ou clicando no fundo. */
export function Modal({ aberto, titulo, onFechar, children, rodape }) {
  const caixaRef = useRef(null);

  useEffect(() => {
    if (!aberto) return;

    const aoTeclar = (evento) => {
      if (evento.key === "Escape") onFechar?.();
    };
    document.addEventListener("keydown", aoTeclar);

    // Trava a rolagem do fundo enquanto o modal esta aberto.
    const overflowAnterior = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Leva o foco para dentro do dialogo; sem isso o teclado continua
    // navegando pela pagina atras dele.
    caixaRef.current?.focus();

    return () => {
      document.removeEventListener("keydown", aoTeclar);
      document.body.style.overflow = overflowAnterior;
    };
  }, [aberto, onFechar]);

  if (!aberto) return null;

  return (
    <div className="modal__fundo" onMouseDown={(e) => e.target === e.currentTarget && onFechar?.()}>
      <div
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        tabIndex={-1}
        ref={caixaRef}
      >
        <header className="modal__topo">
          <h3 className="modal__titulo">{titulo}</h3>
          <button type="button" className="modal__fechar" onClick={onFechar} aria-label="Fechar">
            &times;
          </button>
        </header>
        <div className="modal__corpo">{children}</div>
        {rodape && <footer className="modal__rodape">{rodape}</footer>}
      </div>
    </div>
  );
}
