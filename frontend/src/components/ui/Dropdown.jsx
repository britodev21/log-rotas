import { useEffect, useRef, useState } from "react";

import "./Dropdown.css";

/**
 * Menu suspenso.
 *
 * Fecha ao clicar fora, ao pressionar Esc e ao escolher um item. Navegável
 * por teclado com as setas, porque o menu do usuário fica na topbar e é um
 * dos caminhos para sair do sistema.
 */
export function Dropdown({ gatilho, children, alinhamento = "direita", largura = 216 }) {
  const [aberto, setAberto] = useState(false);
  const areaRef = useRef(null);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!aberto) return;

    const aoClicarFora = (evento) => {
      if (!areaRef.current?.contains(evento.target)) setAberto(false);
    };
    const aoTeclar = (evento) => {
      if (evento.key === "Escape") {
        setAberto(false);
        return;
      }
      if (evento.key !== "ArrowDown" && evento.key !== "ArrowUp") return;

      evento.preventDefault();
      const itens = [...(menuRef.current?.querySelectorAll("[data-item]") ?? [])];
      if (itens.length === 0) return;

      const atual = itens.indexOf(document.activeElement);
      const proximo =
        evento.key === "ArrowDown"
          ? (atual + 1) % itens.length
          : (atual - 1 + itens.length) % itens.length;
      itens[proximo].focus();
    };

    document.addEventListener("mousedown", aoClicarFora);
    document.addEventListener("keydown", aoTeclar);
    return () => {
      document.removeEventListener("mousedown", aoClicarFora);
      document.removeEventListener("keydown", aoTeclar);
    };
  }, [aberto]);

  return (
    <div className="menu-area" ref={areaRef}>
      <div
        onClick={() => setAberto((v) => !v)}
        role="button"
        tabIndex={0}
        aria-haspopup="menu"
        aria-expanded={aberto}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setAberto((v) => !v);
          }
        }}
      >
        {gatilho}
      </div>

      {aberto && (
        <div
          className={`menu menu--${alinhamento}`}
          style={{ width: largura }}
          role="menu"
          ref={menuRef}
          onClick={() => setAberto(false)}
        >
          {children}
        </div>
      )}
    </div>
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
