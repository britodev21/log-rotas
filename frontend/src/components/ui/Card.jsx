import "./Card.css";

export function Card({ titulo, descricao, acoes, children, className = "" }) {
  return (
    <section className={`cartao ${className}`}>
      {(titulo || acoes) && (
        <header className="cartao__topo">
          <div>
            {titulo && <h3 className="cartao__titulo">{titulo}</h3>}
            {descricao && <p className="cartao__descricao">{descricao}</p>}
          </div>
          {acoes && <div className="cartao__acoes">{acoes}</div>}
        </header>
      )}
      <div className="cartao__corpo">{children}</div>
    </section>
  );
}

/**
 * Estado vazio — usado tambem para dizer, sem rodeios, o que ainda nao existe.
 *
 * Preferimos isso a inventar dados de demonstracao: uma tela que mostra numero
 * falso ensina o usuario a confiar em coisa que nao existe.
 */
export function EmptyState({ titulo, children, acao }) {
  return (
    <div className="vazio">
      <h4 className="vazio__titulo">{titulo}</h4>
      {children && <div className="vazio__texto">{children}</div>}
      {acao && <div className="vazio__acao">{acao}</div>}
    </div>
  );
}
