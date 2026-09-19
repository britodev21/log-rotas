import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";

import { Button } from "./Button";
import "./Modal.css";

const DURACAO_SAIDA = 160;

/**
 * Caixa de diálogo modal.
 *
 * Detalhes que separam um modal acabado de um `display: none`:
 *
 * - anima na entrada **e na saída**; sumir instantaneamente faz parecer que
 *   a tela piscou;
 * - prende o Tab dentro do diálogo, senão o teclado continua navegando pela
 *   página atrás dele;
 * - devolve o foco ao elemento que abriu, para quem usa teclado não ser
 *   jogado de volta ao topo da página;
 * - trava a rolagem do fundo compensando a largura da barra, senão a página
 *   inteira desloca alguns pixels ao abrir;
 * - é renderizado num portal no `body`.
 *
 * O portal não é preferência de estilo, é correção de um defeito real:
 * `position: fixed` deixa de ser relativo à janela quando QUALQUER ancestral
 * tem `transform`, `filter` ou `backdrop-filter` — esse ancestral vira o
 * bloco contentor. O modal ficava dentro de `.transicao`, que retinha um
 * `transform` da animação de entrada da página, e por isso se centralizava
 * na coluna de conteúdo em vez da tela, com o fundo escuro sem cobrir a
 * barra lateral. No `body` não há ancestral que possa causar isso.
 */
export function Modal({
  aberto,
  titulo,
  descricao,
  onFechar,
  children,
  rodape,
  tamanho = "md",
}) {
  const [montado, setMontado] = useState(aberto);
  const [saindo, setSaindo] = useState(false);
  const caixaRef = useRef(null);
  const focoAnteriorRef = useRef(null);

  useEffect(() => {
    if (aberto) {
      focoAnteriorRef.current = document.activeElement;
      setMontado(true);
      setSaindo(false);
    } else if (montado) {
      setSaindo(true);
      const id = setTimeout(() => {
        setMontado(false);
        setSaindo(false);
        focoAnteriorRef.current?.focus?.();
      }, DURACAO_SAIDA);
      return () => clearTimeout(id);
    }
  }, [aberto, montado]);

  const aoTeclar = useCallback(
    (evento) => {
      if (evento.key === "Escape") {
        evento.stopPropagation();
        onFechar?.();
        return;
      }
      if (evento.key !== "Tab") return;

      const focaveis = caixaRef.current?.querySelectorAll(
        'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
      );
      if (!focaveis?.length) return;

      const primeiro = focaveis[0];
      const ultimo = focaveis[focaveis.length - 1];

      if (evento.shiftKey && document.activeElement === primeiro) {
        evento.preventDefault();
        ultimo.focus();
      } else if (!evento.shiftKey && document.activeElement === ultimo) {
        evento.preventDefault();
        primeiro.focus();
      }
    },
    [onFechar],
  );

  useEffect(() => {
    if (!montado) return;

    const larguraBarra = window.innerWidth - document.documentElement.clientWidth;
    const overflowAnterior = document.body.style.overflow;
    const padAnterior = document.body.style.paddingRight;
    document.body.style.overflow = "hidden";
    if (larguraBarra > 0) document.body.style.paddingRight = `${larguraBarra}px`;

    // Foca o primeiro campo, se houver; senão a própria caixa.
    const primeiroCampo = caixaRef.current?.querySelector(
      "input:not([type='hidden']):not([disabled]), select:not([disabled]), textarea:not([disabled])",
    );
    (primeiroCampo ?? caixaRef.current)?.focus();

    return () => {
      document.body.style.overflow = overflowAnterior;
      document.body.style.paddingRight = padAnterior;
    };
  }, [montado]);

  if (!montado) return null;

  return createPortal(
    <div
      className={`modal-fundo ${saindo ? "modal-fundo--saindo" : ""}`}
      onMouseDown={(e) => e.target === e.currentTarget && onFechar?.()}
    >
      <div
        className={`modal modal--${tamanho} ${saindo ? "modal--saindo" : ""}`}
        role="dialog"
        aria-modal="true"
        aria-label={titulo}
        tabIndex={-1}
        ref={caixaRef}
        onKeyDown={aoTeclar}
      >
        <header className="modal__topo">
          <div className="modal__identificacao">
            <h3 className="modal__titulo">{titulo}</h3>
            {descricao && <p className="modal__descricao">{descricao}</p>}
          </div>
          <Button
            variante="sutil"
            tamanho="sm"
            icone={X}
            onClick={onFechar}
            aria-label="Fechar"
          />
        </header>

        <div className="modal__corpo">{children}</div>

        {rodape && <footer className="modal__rodape">{rodape}</footer>}
      </div>
    </div>,
    document.body,
  );
}
