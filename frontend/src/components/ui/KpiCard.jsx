import "./KpiCard.css";

/**
 * Indicador operacional.
 *
 * Compacto de proposito: o painel mostra varios lado a lado, e cartao
 * gigante com numero enorme ocupa a tela toda para transmitir um numero so.
 * A hierarquia e: rotulo pequeno, numero em destaque, contexto abaixo.
 */
export function KpiCard({
  rotulo,
  valor,
  unidade,
  contexto,
  icone: Icone,
  tom = "neutro",
  carregando = false,
  aoClicar,
}) {
  const Tag = aoClicar ? "button" : "div";

  return (
    <Tag
      className={`kpi kpi--${tom} ${aoClicar ? "kpi--clicavel" : ""}`}
      onClick={aoClicar}
      type={aoClicar ? "button" : undefined}
    >
      <div className="kpi__topo">
        <span className="kpi__rotulo">{rotulo}</span>
        {Icone && (
          <span className="kpi__icone" aria-hidden="true">
            <Icone size={15} strokeWidth={2} />
          </span>
        )}
      </div>

      <div className="kpi__valor">
        {carregando ? (
          <span className="kpi__vazio" aria-hidden="true" />
        ) : (
          <>
            <span className="numero">{valor}</span>
            {unidade && <span className="kpi__unidade">{unidade}</span>}
          </>
        )}
      </div>

      {contexto && <span className="kpi__contexto">{contexto}</span>}
    </Tag>
  );
}
