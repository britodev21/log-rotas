import "./Spinner.css";

/**
 * Indicador de atividade curta (dentro de botao, campo, linha de tabela).
 *
 * Para espera de tela inteira NAO use spinner: use Skeleton, que mostra a
 * forma do que esta chegando em vez de um circulo girando no vazio.
 */
export function Spinner({ tamanho = 16, className = "" }) {
  return (
    <span
      className={`spinner ${className}`}
      style={{ width: tamanho, height: tamanho }}
      role="status"
      aria-label="Carregando"
    />
  );
}
