import "./Skeleton.css";

/**
 * Esqueletos de carregamento.
 *
 * Substituem o "Carregando..." em texto. A diferenca nao e estetica: o
 * esqueleto mostra a forma do que esta chegando, entao a tela nao salta
 * quando o dado chega, e a espera parece mais curta do que e.
 *
 * Todos sao marcados com aria-hidden e acompanhados de um aviso para leitor
 * de tela — a forma visual nao significa nada para quem nao a ve.
 */
function Aviso({ texto = "Carregando" }) {
  return (
    <span className="sr-apenas" role="status" aria-live="polite">
      {texto}
    </span>
  );
}

/** Bloco cru, para montar esqueletos sob medida. */
export function Skeleton({ largura = "100%", altura = 12, raio = "var(--r-sm)", className = "" }) {
  return (
    <span
      className={`osso ${className}`}
      style={{ width: largura, height: altura, borderRadius: raio }}
      aria-hidden="true"
    />
  );
}

export function SkeletonText({ linhas = 3, className = "" }) {
  return (
    <div className={`osso-texto ${className}`}>
      {Array.from({ length: linhas }, (_, i) => (
        <Skeleton
          key={i}
          // A ultima linha sai mais curta, como acontece num paragrafo real.
          largura={i === linhas - 1 ? "62%" : "100%"}
          altura={10}
        />
      ))}
      <Aviso />
    </div>
  );
}

export function SkeletonCard({ comIcone = true }) {
  return (
    <div className="osso-cartao" aria-hidden="true">
      <div className="osso-cartao__topo">
        <Skeleton largura={84} altura={10} />
        {comIcone && <Skeleton largura={28} altura={28} raio="var(--r-md)" />}
      </div>
      <Skeleton largura={64} altura={24} />
      <Skeleton largura={110} altura={9} />
    </div>
  );
}

export function SkeletonList({ itens = 4 }) {
  return (
    <div className="osso-lista">
      {Array.from({ length: itens }, (_, i) => (
        <div className="osso-lista__item" key={i} aria-hidden="true">
          <Skeleton largura={32} altura={32} raio="var(--r-total)" />
          <div className="osso-lista__texto">
            <Skeleton largura="42%" altura={10} />
            <Skeleton largura="66%" altura={9} />
          </div>
          <Skeleton largura={68} altura={20} raio="var(--r-sm)" />
        </div>
      ))}
      <Aviso />
    </div>
  );
}

export function SkeletonTable({ linhas = 5, colunas = 4 }) {
  return (
    <div className="osso-tabela">
      <div className="osso-tabela__cabecalho" aria-hidden="true">
        {Array.from({ length: colunas }, (_, c) => (
          <Skeleton key={c} largura={c === 0 ? "38%" : "56%"} altura={9} />
        ))}
      </div>
      {Array.from({ length: linhas }, (_, l) => (
        <div className="osso-tabela__linha" key={l} aria-hidden="true">
          {Array.from({ length: colunas }, (_, c) => (
            <Skeleton key={c} largura={c === 0 ? "72%" : "48%"} altura={11} />
          ))}
        </div>
      ))}
      <Aviso texto="Carregando tabela" />
    </div>
  );
}

export function SkeletonMap({ altura = 380 }) {
  return (
    <div className="osso-mapa" style={{ height: altura }} aria-hidden="true">
      <div className="osso-mapa__grade" />
      <Aviso texto="Carregando mapa" />
    </div>
  );
}

export function SkeletonPage() {
  return (
    <div className="osso-pagina">
      <div className="osso-pagina__cabecalho" aria-hidden="true">
        <Skeleton largura={220} altura={22} />
        <Skeleton largura={320} altura={11} />
      </div>
      <div className="osso-pagina__kpis">
        {Array.from({ length: 4 }, (_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
      <SkeletonMap />
      <Aviso texto="Carregando pagina" />
    </div>
  );
}
