import "./Badge.css";

/**
 * Etiqueta de status.
 *
 * tom: "neutro" | "info" | "sucesso" | "atencao" | "erro"
 *
 * As cores vem dos mesmos tokens usados pelos status de entrega, para que
 * verde signifique "entregue" na lista, no mapa e na tela do motorista.
 */
export function Badge({ tom = "neutro", children }) {
  return <span className={`etiqueta etiqueta--${tom}`}>{children}</span>;
}
