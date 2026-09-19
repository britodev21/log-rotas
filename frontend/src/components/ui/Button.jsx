import "./Button.css";

/**
 * Botao da aplicacao.
 *
 * variante: "primario" | "secundario" | "perigo" | "texto"
 * tamanho:  "normal" | "grande"  ("grande" e o usado na tela do motorista)
 */
export function Button({
  children,
  variante = "primario",
  tamanho = "normal",
  carregando = false,
  larguraTotal = false,
  type = "button",
  disabled,
  className = "",
  ...resto
}) {
  const classes = [
    "botao",
    `botao--${variante}`,
    `botao--${tamanho}`,
    larguraTotal ? "botao--largo" : "",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type={type}
      className={classes}
      disabled={disabled || carregando}
      aria-busy={carregando || undefined}
      {...resto}
    >
      {carregando && <span className="botao__girando" aria-hidden="true" />}
      {children}
    </button>
  );
}
