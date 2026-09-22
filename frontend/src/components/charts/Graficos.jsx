/**
 * Gráficos do relatório, em CSS puro — sem biblioteca.
 *
 * São duas formas, e só duas, porque são as que respondem as perguntas do
 * relatório: uma série de dias (colunas empilhadas) e uma comparação de
 * categorias (barras horizontais rotuladas).
 *
 * Regras que valem para as duas, e o porquê:
 *
 * - **A cor nunca é o único sinal.** Cada barra horizontal tem o rótulo ao
 *   lado; as colunas têm legenda e tabela. Quem não distingue as cores lê o
 *   mesmo número.
 * - **As cores das séries são `--serie-1` e `--serie-2`**, escolhidas para
 *   se separarem em daltonismo (ver tokens.css). Verde/vermelho, que seria
 *   o óbvio para entregue/não entregue, não se separa.
 * - **Número em cima de tudo, não.** O valor aparece no fim da barra
 *   horizontal (onde é a informação) e no toque/hover da coluna.
 * - **Grade discreta:** a linha de base existe, o resto não compete com o
 *   dado.
 */

import { useId, useState } from "react";

import "./graficos.css";

const SEM_DADO = "—";

/** Barra horizontal rotulada: comparação de poucas categorias. */
export function BarrasRotuladas({ itens, formatar = (v) => v, cor = "var(--serie-1)" }) {
  const maximo = Math.max(...itens.map((i) => i.valor), 1);

  return (
    <ul className="gr-barras">
      {itens.map((item) => (
        <li className="gr-barra" key={item.rotulo}>
          <span className="gr-barra__rotulo">{item.rotulo}</span>
          <span className="gr-barra__trilho">
            <span
              className="gr-barra__preenchimento"
              style={{
                width: `${Math.max((item.valor / maximo) * 100, item.valor > 0 ? 2 : 0)}%`,
                background: item.cor ?? cor,
              }}
            />
          </span>
          <span className="gr-barra__valor numero">{formatar(item.valor)}</span>
          {item.detalhe && <span className="gr-barra__detalhe">{item.detalhe}</span>}
        </li>
      ))}
    </ul>
  );
}

/**
 * Colunas empilhadas por dia: duas séries, mesma unidade.
 *
 * Duas séries e uma escala só. Duas escalas no mesmo gráfico — entregas de
 * um lado, quilômetros do outro — deixam qualquer relação parecer verdade
 * conforme a escala escolhida.
 */
export function ColunasPorDia({ dias, series, formatarDia }) {
  const [ativo, setAtivo] = useState(null);
  const idBase = useId();
  const total = (d) => series.reduce((soma, s) => soma + (d[s.chave] ?? 0), 0);
  const maximo = Math.max(...dias.map(total), 1);

  return (
    <div className="gr-colunas">
      <div className="gr-colunas__area" role="group" aria-label="Entregas por dia">
        {dias.map((dia, indice) => {
          const soma = total(dia);
          const destacado = ativo === indice;
          return (
            <div
              className={`gr-coluna ${destacado ? "gr-coluna--ativa" : ""}`}
              key={dia.dia}
              onMouseEnter={() => setAtivo(indice)}
              onMouseLeave={() => setAtivo(null)}
              onFocus={() => setAtivo(indice)}
              onBlur={() => setAtivo(null)}
              tabIndex={0}
              aria-describedby={destacado ? `${idBase}-dica` : undefined}
            >
              <div className="gr-coluna__pilha">
                {series.map((serie) => {
                  const valor = dia[serie.chave] ?? 0;
                  if (!valor) return null;
                  return (
                    <div
                      key={serie.chave}
                      className="gr-coluna__segmento"
                      style={{
                        height: `${(valor / maximo) * 100}%`,
                        background: serie.cor,
                      }}
                    />
                  );
                })}
              </div>
              <span className="gr-coluna__rotulo">{formatarDia(dia.dia)}</span>
              {destacado && (
                <div className="gr-dica" id={`${idBase}-dica`} role="tooltip">
                  <strong>{formatarDia(dia.dia, true)}</strong>
                  {series.map((serie) => (
                    <span key={serie.chave}>
                      <i style={{ background: serie.cor }} aria-hidden="true" />
                      {serie.rotulo}: <b className="numero">{dia[serie.chave] ?? 0}</b>
                    </span>
                  ))}
                  <span className="gr-dica__total">
                    total <b className="numero">{soma}</b>
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <Legenda series={series} />
    </div>
  );
}

export function Legenda({ series }) {
  return (
    <ul className="gr-legenda">
      {series.map((serie) => (
        <li key={serie.chave}>
          <i style={{ background: serie.cor }} aria-hidden="true" />
          {serie.rotulo}
        </li>
      ))}
    </ul>
  );
}

/**
 * Duas medidas lado a lado: o planejado e o realizado.
 *
 * É a forma da calibração — e a única em que a comparação importa mais que
 * o valor, por isso as duas barras dividem a mesma escala.
 */
export function ComparacaoPlanejadoReal({ planejado, real, formatar, rotulos }) {
  const maximo = Math.max(planejado ?? 0, real ?? 0, 1);
  const linhas = [
    { rotulo: rotulos?.[0] ?? "Planejado", valor: planejado, cor: "var(--serie-1)" },
    { rotulo: rotulos?.[1] ?? "Real", valor: real, cor: "var(--serie-2)" },
  ];

  return (
    <ul className="gr-barras gr-barras--comparacao">
      {linhas.map((linha) => (
        <li className="gr-barra" key={linha.rotulo}>
          <span className="gr-barra__rotulo">{linha.rotulo}</span>
          <span className="gr-barra__trilho">
            <span
              className="gr-barra__preenchimento"
              style={{
                width: `${((linha.valor ?? 0) / maximo) * 100}%`,
                background: linha.cor,
              }}
            />
          </span>
          <span className="gr-barra__valor numero">
            {linha.valor == null ? SEM_DADO : formatar(linha.valor)}
          </span>
        </li>
      ))}
    </ul>
  );
}
