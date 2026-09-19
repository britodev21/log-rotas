import {
  cloneElement,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import "./Dropdown.css";

const MARGEM = 6;
const BORDA_JANELA = 8;

/**
 * Menu suspenso.
 *
 * O menu é renderizado num portal no `body`, e não ao lado do gatilho.
 *
 * O motivo é concreto: dentro da tabela ele fica sob dois contextos que
 * recortam — `overflow-x: auto` na área rolável e `overflow: hidden` no corpo
 * do cartão. Um elemento posicionado por `absolute` é cortado por qualquer
 * ancestral com overflow, então o menu aparecia escondido atrás da tabela.
 * `z-index` não resolve isso: recorte acontece antes do empilhamento.
 *
 * Com o portal, o menu sai da árvore que o recortava e é posicionado por
 * coordenadas de tela, calculadas a partir do retângulo do gatilho.
 */
export function Dropdown({ gatilho, children, alinhamento = "direita", largura = 216 }) {
  const [aberto, setAberto] = useState(false);
  const [posicao, setPosicao] = useState(null);
  const gatilhoRef = useRef(null);
  const menuRef = useRef(null);

  const calcularPosicao = useCallback(() => {
    const alvo = gatilhoRef.current;
    if (!alvo) return;

    const r = alvo.getBoundingClientRect();
    const alturaMenu = menuRef.current?.offsetHeight ?? 0;

    // Abre para baixo; se não couber, vira para cima em vez de vazar da tela.
    const cabeAbaixo = r.bottom + MARGEM + alturaMenu <= window.innerHeight - BORDA_JANELA;
    const paraCima = alturaMenu > 0 && !cabeAbaixo;

    const top = paraCima ? r.top - MARGEM - alturaMenu : r.bottom + MARGEM;

    let left = alinhamento === "direita" ? r.right - largura : r.left;
    // Mantém o menu dentro da janela mesmo com o gatilho na borda.
    left = Math.min(
      Math.max(BORDA_JANELA, left),
      window.innerWidth - largura - BORDA_JANELA,
    );

    setPosicao({ top, left, paraCima });
  }, [alinhamento, largura]);

  // Layout effect: posiciona antes da pintura, senão o menu aparece por um
  // quadro no canto errado e "salta" para o lugar.
  useLayoutEffect(() => {
    if (aberto) calcularPosicao();
  }, [aberto, calcularPosicao]);

  useEffect(() => {
    if (!aberto) return;

    const fora = (alvo) =>
      !gatilhoRef.current?.contains(alvo) && !menuRef.current?.contains(alvo);

    const aoClicar = (evento) => {
      if (fora(evento.target)) setAberto(false);
    };

    const aoTeclar = (evento) => {
      if (evento.key === "Escape") {
        setAberto(false);
        // A ancora e um <span>, que nao recebe foco: devolve para o botao.
        gatilhoRef.current?.querySelector("button")?.focus();
        return;
      }
      if (evento.key !== "ArrowDown" && evento.key !== "ArrowUp") return;

      evento.preventDefault();
      const itens = [...(menuRef.current?.querySelectorAll("[data-item]:not([disabled])") ?? [])];
      if (itens.length === 0) return;

      const atual = itens.indexOf(document.activeElement);
      const proximo =
        evento.key === "ArrowDown"
          ? (atual + 1) % itens.length
          : (atual - 1 + itens.length) % itens.length;
      itens[proximo].focus();
    };

    // `capture` para acompanhar rolagem de qualquer ancestral, inclusive a
    // rolagem horizontal da própria tabela.
    const aoMover = () => calcularPosicao();

    document.addEventListener("mousedown", aoClicar);
    document.addEventListener("keydown", aoTeclar);
    window.addEventListener("scroll", aoMover, true);
    window.addEventListener("resize", aoMover);

    return () => {
      document.removeEventListener("mousedown", aoClicar);
      document.removeEventListener("keydown", aoTeclar);
      window.removeEventListener("scroll", aoMover, true);
      window.removeEventListener("resize", aoMover);
    };
  }, [aberto, calcularPosicao]);

  function alternar() {
    setAberto((v) => !v);
  }

  return (
    <>
      {/* O gatilho recebido ja e um <button>. Envolve-lo num div com
          role="button" criaria dois elementos focaveis aninhados: duas
          paradas de Tab e semantica ambigua no leitor de tela. Em vez disso
          as propriedades aria vao no proprio botao, que ja responde a Enter
          e Espaco nativamente. O div serve apenas de ancora para medir a
          posicao. */}
      <span ref={gatilhoRef} className="menu-gatilho">
        {cloneElement(gatilho, {
          onClick: alternar,
          "aria-haspopup": "menu",
          "aria-expanded": aberto,
        })}
      </span>

      {aberto &&
        createPortal(
          <div
            ref={menuRef}
            className={`menu ${posicao?.paraCima ? "menu--acima" : ""} menu--${alinhamento}`}
            style={{
              width: largura,
              top: posicao?.top ?? -9999,
              left: posicao?.left ?? -9999,
              // Enquanto a posição não foi medida o menu fica invisível, em
              // vez de piscar no canto superior esquerdo.
              visibility: posicao ? "visible" : "hidden",
            }}
            role="menu"
            onClick={() => setAberto(false)}
          >
            {children}
          </div>,
          document.body,
        )}
    </>
  );
}

export function DropdownItem({ icone: Icone, children, onClick, perigo = false, ...resto }) {
  return (
    <button
      type="button"
      className={`menu__item ${perigo ? "menu__item--perigo" : ""}`}
      role="menuitem"
      data-item
      onClick={onClick}
      {...resto}
    >
      {Icone && <Icone size={15} strokeWidth={2} aria-hidden="true" />}
      <span>{children}</span>
    </button>
  );
}

export function DropdownLabel({ children }) {
  return <div className="menu__rotulo">{children}</div>;
}

export function DropdownSeparator() {
  return <div className="menu__separador" role="separator" />;
}
