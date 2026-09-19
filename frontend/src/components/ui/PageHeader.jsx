import "./PageHeader.css";

/** Cabecalho padrao das telas administrativas. */
export function PageHeader({ titulo, descricao, acoes }) {
  return (
    <header className="cabecalho-pagina">
      <div>
        <h1 className="cabecalho-pagina__titulo">{titulo}</h1>
        {descricao && <p className="cabecalho-pagina__descricao">{descricao}</p>}
      </div>
      {acoes && <div className="cabecalho-pagina__acoes">{acoes}</div>}
    </header>
  );
}
