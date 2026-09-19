import "./Alert.css";

/** tom: "erro" | "sucesso" | "atencao" | "info" */
export function Alert({ tom = "info", titulo, children }) {
  // Erro e atencao sao anunciados na hora pelo leitor de tela; informacao
  // comum espera a leitura chegar ate ela.
  const urgente = tom === "erro" || tom === "atencao";

  return (
    <div
      className={`aviso aviso--${tom}`}
      role={urgente ? "alert" : "status"}
      aria-live={urgente ? "assertive" : "polite"}
    >
      {titulo && <strong className="aviso__titulo">{titulo}</strong>}
      <div className="aviso__corpo">{children}</div>
    </div>
  );
}
