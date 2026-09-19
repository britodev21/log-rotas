import "./Card.css";

/**
 * Superficie de conteudo.
 *
 * `interativo` liga a microinteracao de hover (elevacao minima e borda mais
 * definida). So use em cartao que realmente responde ao clique — elevar
 * algo que nao faz nada promete interacao que nao existe.
 */
export function Card({
  titulo,
  descricao,
  acoes,
  rodape,
  interativo = false,
  semPadding = false,
  children,
  className = "",
  ...resto
}) {
  const classes = [
    "cartao",
    interativo && "cartao--interativo",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <section className={classes} {...resto}>
      {(titulo || acoes) && (
        <header className="cartao__topo">
          <div className="cartao__identificacao">
            {titulo && <h3 className="cartao__titulo">{titulo}</h3>}
            {descricao && <p className="cartao__descricao">{descricao}</p>}
          </div>
          {acoes && <div className="cartao__acoes">{acoes}</div>}
        </header>
      )}

      <div className={semPadding ? "cartao__corpo cartao__corpo--cru" : "cartao__corpo"}>
        {children}
      </div>

      {rodape && <footer className="cartao__rodape">{rodape}</footer>}
    </section>
  );
}
