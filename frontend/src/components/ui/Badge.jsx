import "./Badge.css";

/**
 * Etiqueta genérica.
 *
 * tom: neutro | info | sucesso | atencao | perigo | marca
 */
export function Badge({ tom = "neutro", ponto = false, children, className = "" }) {
  return (
    <span className={`etq etq--${tom} ${className}`}>
      {ponto && <span className="etq__ponto" aria-hidden="true" />}
      {children}
    </span>
  );
}

/**
 * Mapa único de status do domínio para rótulo e cor.
 *
 * Existe aqui, num lugar só, para que "Entregue" seja verde na lista, no
 * mapa, no painel e na tela do motorista. Espalhar esse mapeamento pelas
 * telas é o caminho mais curto para a mesma palavra aparecer em duas cores
 * diferentes no mesmo sistema.
 *
 * Os valores em MAIÚSCULA são os do banco (ASCII, sem acento); o rótulo é a
 * forma que a pessoa lê.
 */
export const STATUS_ENTREGA = {
  PENDENTE: { rotulo: "Pendente", tom: "neutro" },
  PLANEJADA: { rotulo: "Planejada", tom: "info" },
  EM_ROTA: { rotulo: "Em rota", tom: "atencao" },
  CHEGOU: { rotulo: "No local", tom: "atencao" },
  ENTREGUE: { rotulo: "Entregue", tom: "sucesso" },
  NAO_ENTREGUE: { rotulo: "Não entregue", tom: "perigo" },
  CANCELADA: { rotulo: "Cancelada", tom: "neutro" },
};

export const STATUS_ROTA = {
  RASCUNHO: { rotulo: "Rascunho", tom: "neutro" },
  PLANEJADA: { rotulo: "Planejada", tom: "info" },
  INICIADA: { rotulo: "Em andamento", tom: "atencao" },
  FINALIZADA: { rotulo: "Finalizada", tom: "sucesso" },
  CANCELADA: { rotulo: "Cancelada", tom: "neutro" },
};

export const STATUS_USUARIO = {
  ATIVO: { rotulo: "Ativo", tom: "sucesso" },
  INATIVO: { rotulo: "Inativo", tom: "neutro" },
};

const MAPAS = {
  entrega: STATUS_ENTREGA,
  rota: STATUS_ROTA,
  usuario: STATUS_USUARIO,
};

/**
 * Etiqueta de status do domínio.
 *
 * <StatusBadge tipo="entrega" valor="EM_ROTA" />
 *
 * Status desconhecido não quebra a tela nem some: aparece em tom neutro com
 * o próprio código, o que torna o problema visível em vez de silencioso.
 */
export function StatusBadge({ tipo = "entrega", valor, ponto = true }) {
  const definicao = MAPAS[tipo]?.[valor] ?? { rotulo: valor ?? "—", tom: "neutro" };
  return (
    <Badge tom={definicao.tom} ponto={ponto}>
      {definicao.rotulo}
    </Badge>
  );
}
