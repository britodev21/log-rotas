import "./PageHeader.css";

/** Cabecalho padrao das telas administrativas. */
export function PageHeader({ titulo, descricao, acoes, children }) {
  return (
    <header className="cab">
      <div className="cab__identificacao">
        <h1 className="cab__titulo">{titulo}</h1>
        {descricao && <p className="cab__descricao">{descricao}</p>}
      </div>
      {children}
      {acoes && <div className="cab__acoes">{acoes}</div>}
    </header>
  );
}
