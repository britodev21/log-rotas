import { forwardRef } from "react";

import { Spinner } from "./Spinner";
import "./Button.css";

/**
 * Botão do sistema.
 *
 * variante: primario | secundario | sutil | perigo | texto
 * tamanho:  sm | md | lg        (lg é o usado na tela do motorista)
 *
 * Durante o carregamento o botão fica desabilitado, o que impede o clique
 * duplo que dispararia a operação duas vezes. O rótulo permanece no lugar e
 * apenas o ícone vira spinner, para a largura não mudar e a linha não
 * "pular" no meio da ação.
 */
export const Button = forwardRef(function Button(
  {
    children,
    variante = "primario",
    tamanho = "md",
    icone: Icone,
    iconeDireita: IconeDireita,
    carregando = false,
    larguraTotal = false,
    type = "button",
    disabled,
    className = "",
    ...resto
  },
  ref,
) {
  const apenasIcone = !children && (Icone || IconeDireita);

  const classes = [
    "bt",
    `bt--${variante}`,
    `bt--${tamanho}`,
    larguraTotal && "bt--largo",
    apenasIcone && "bt--icone",
    carregando && "bt--carregando",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const tamanhoIcone = tamanho === "lg" ? 19 : tamanho === "sm" ? 14 : 16;

  return (
    <button
      ref={ref}
      type={type}
      className={classes}
      disabled={disabled || carregando}
      aria-busy={carregando || undefined}
      {...resto}
    >
      {carregando ? (
        <Spinner tamanho={tamanhoIcone} />
      ) : (
        Icone && <Icone size={tamanhoIcone} strokeWidth={2} aria-hidden="true" />
      )}
      {children && <span className="bt__rotulo">{children}</span>}
      {!carregando && IconeDireita && (
        <IconeDireita size={tamanhoIcone} strokeWidth={2} aria-hidden="true" />
      )}
    </button>
  );
});
