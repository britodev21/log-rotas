import "./Table.css";

/**
 * Tabela de dados.
 *
 * Extraída para componente porque a partir da Fase 3 ela aparece em
 * entregas, rotas, motoristas, veículos e clientes — deixá-la como CSS
 * solto garantiria cinco tabelas ligeiramente diferentes.
 *
 * Linhas separadas por uma única hairline, sem grade vertical: coluna
 * alinhada já separa dado o suficiente, e a grade fecha a tabela numa
 * planilha.
 */
export function Table({ children, className = "" }) {
  return (
    <div className="tb-area">
      <table className={`tb ${className}`}>{children}</table>
    </div>
  );
}

export function THead({ children }) {
  return (
    <thead className="tb__cabeca">
      <tr>{children}</tr>
    </thead>
  );
}

export function TH({ children, alinhamento = "left", largura, numerico = false }) {
  return (
    <th
      className={`tb__th ${numerico ? "tb__th--numero" : ""}`}
      style={{ textAlign: alinhamento, width: largura }}
      scope="col"
    >
      {children}
    </th>
  );
}

export function TBody({ children }) {
  return <tbody className="tb__corpo">{children}</tbody>;
}

export function TR({ children, aoClicar, selecionada = false }) {
  return (
    <tr
      className={`tb__tr ${aoClicar ? "tb__tr--clicavel" : ""} ${
        selecionada ? "tb__tr--selecionada" : ""
      }`}
      onClick={aoClicar}
      tabIndex={aoClicar ? 0 : undefined}
      onKeyDown={
        aoClicar
          ? (e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                aoClicar(e);
              }
            }
          : undefined
      }
    >
      {children}
    </tr>
  );
}

export function TD({ children, alinhamento = "left", numerico = false, className = "" }) {
  return (
    <td
      className={`tb__td ${numerico ? "tb__td--numero" : ""} ${className}`}
      style={{ textAlign: alinhamento }}
    >
      {children}
    </td>
  );
}

/** Célula com identificação principal e uma linha secundária abaixo. */
export function TDPrincipal({ principal, secundario }) {
  return (
    <td className="tb__td">
      <span className="tb__principal">{principal}</span>
      {secundario && <span className="tb__secundario">{secundario}</span>}
    </td>
  );
}

/**
 * Coluna de ações.
 *
 * As ações só ganham opacidade plena no hover da linha ou quando recebem
 * foco pelo teclado — assim a tabela fica limpa na leitura, sem esconder a
 * ação de quem navega sem mouse.
 */
export function TDAcoes({ children }) {
  return (
    <td className="tb__td tb__td--acoes">
      <div className="tb__acoes">{children}</div>
    </td>
  );
}
