/**
 * Marca do Log Rotas.
 *
 * O simbolo e um caminho entre dois nos: a origem preenchida, o destino
 * vazado, ligados por uma linha pontilhada. Traz a ideia de rota e
 * sequencia sem recorrer a caminhao ou pin de mapa.
 */
export function Logo({ tamanho = 28, comTexto = true, className = "" }) {
  return (
    <span className={`marca ${className}`} style={{ display: "inline-flex", alignItems: "center", gap: "10px" }}>
      <svg
        width={tamanho}
        height={tamanho}
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden="true"
        style={{ flexShrink: 0 }}
      >
        <rect width="32" height="32" rx="8" fill="var(--primaria)" />
        <path
          d="M9 22.5c0-5 4-5 7-5s7 0 7-5"
          stroke="var(--primaria-texto)"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeDasharray="0.1 5.2"
        />
        <circle cx="9" cy="22.5" r="3.1" fill="var(--primaria-texto)" />
        <circle
          cx="23"
          cy="9.5"
          r="3.1"
          stroke="var(--primaria-texto)"
          strokeWidth="2.4"
        />
      </svg>
      {comTexto && (
        <span
          style={{
            fontSize: "var(--t-16)",
            fontWeight: "var(--p-600)",
            letterSpacing: "var(--tr-titulo)",
            color: "var(--texto)",
          }}
        >
          Log Rotas
        </span>
      )}
    </span>
  );
}
