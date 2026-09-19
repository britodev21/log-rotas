import { AlertCircle, Check } from "lucide-react";

import "./ProcessSteps.css";

/**
 * Acompanhamento de processo em várias etapas.
 *
 * Feito para o cálculo de rotas (Fase 7), onde o backend executa uma
 * sequência real — preparar entregas, conferir endereços, montar a matriz de
 * distâncias, otimizar, gravar o plano — e cada uma pode levar segundos.
 *
 * Regra que este componente impõe: **não existe porcentagem**. O solver não
 * informa progresso contínuo, e inventar uma barra subindo seria mentir
 * sobre o que o sistema sabe. O que ele mostra é o que de fato se sabe: qual
 * etapa terminou, qual está em execução e quais ainda não começaram.
 *
 * Estados de cada etapa: aguardando | executando | concluido | erro
 */
export function ProcessSteps({ etapas = [], className = "" }) {
  return (
    <ol className={`processo ${className}`} aria-live="polite">
      {etapas.map((etapa, indice) => (
        <li
          key={etapa.id ?? indice}
          className={`processo__etapa processo__etapa--${etapa.estado}`}
        >
          <span className="processo__marcador" aria-hidden="true">
            {etapa.estado === "concluido" && <Check size={12} strokeWidth={3} />}
            {etapa.estado === "erro" && <AlertCircle size={12} strokeWidth={2.6} />}
            {etapa.estado === "executando" && <span className="processo__pulso" />}
          </span>

          <div className="processo__texto">
            <span className="processo__nome">{etapa.nome}</span>
            {etapa.detalhe && (
              <span className="processo__detalhe">{etapa.detalhe}</span>
            )}
          </div>

          <span className="sr-apenas">
            {etapa.estado === "concluido" && "concluída"}
            {etapa.estado === "executando" && "em execução"}
            {etapa.estado === "aguardando" && "aguardando"}
            {etapa.estado === "erro" && "falhou"}
          </span>
        </li>
      ))}
    </ol>
  );
}

/** Etapas do cálculo de rotas, na ordem real do pipeline do backend. */
export const ETAPAS_CALCULO = [
  { id: "entregas", nome: "Preparando entregas" },
  { id: "enderecos", nome: "Conferindo endereços" },
  { id: "paradas", nome: "Agrupando paradas" },
  { id: "matriz", nome: "Calculando distâncias e tempos" },
  { id: "otimizacao", nome: "Otimizando rotas" },
  { id: "plano", nome: "Montando o planejamento" },
];

/**
 * Deriva o estado de cada etapa a partir do índice da etapa corrente.
 * Índice -1 = nada começou; índice >= total = tudo concluído.
 */
export function estadosDoCalculo(indiceAtual, { falhou = false } = {}) {
  return ETAPAS_CALCULO.map((etapa, i) => {
    if (i < indiceAtual) return { ...etapa, estado: "concluido" };
    if (i === indiceAtual) return { ...etapa, estado: falhou ? "erro" : "executando" };
    return { ...etapa, estado: "aguardando" };
  });
}
