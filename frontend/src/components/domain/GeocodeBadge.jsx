import { Badge } from "../ui";

/**
 * Situacao da geocodificacao de um endereco.
 *
 * Aparece em cliente, base e (na Fase 3) entrega. Deixar isso visivel desde
 * agora tem proposito: quando a Fase 4 ligar a geocodificacao, a equipe ja
 * vai reconhecer o indicador, e enquanto isso fica claro que nenhum endereco
 * foi convertido em coordenada ainda — em vez de o sistema parecer que sabe
 * onde as coisas ficam.
 */
const MAPA = {
  PENDENTE: { rotulo: "Sem coordenada", tom: "neutro" },
  OK: { rotulo: "Localizado", tom: "sucesso" },
  AMBIGUO: { rotulo: "Ambiguo", tom: "atencao" },
  FALHOU: { rotulo: "Nao localizado", tom: "perigo" },
  MANUAL: { rotulo: "Pino manual", tom: "info" },
};

export function GeocodeBadge({ status, semEndereco = false }) {
  if (semEndereco) {
    return <Badge tom="neutro">Sem endereco</Badge>;
  }
  const definicao = MAPA[status] ?? { rotulo: status ?? "—", tom: "neutro" };
  return (
    <Badge tom={definicao.tom} ponto>
      {definicao.rotulo}
    </Badge>
  );
}
