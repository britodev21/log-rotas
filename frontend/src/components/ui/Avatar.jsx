import "./Avatar.css";

/**
 * Avatar por iniciais.
 *
 * A cor vem de um hash do nome, entao a mesma pessoa tem sempre a mesma cor
 * — o que ajuda a reconhecer motorista na lista sem ler o nome inteiro.
 */
const MATIZES = [214, 262, 292, 340, 12, 32, 152, 188];

function iniciais(nome = "") {
  const partes = nome.trim().split(/\s+/).filter(Boolean);
  if (partes.length === 0) return "?";
  if (partes.length === 1) return partes[0].slice(0, 2).toUpperCase();
  return (partes[0][0] + partes[partes.length - 1][0]).toUpperCase();
}

function matiz(nome = "") {
  let soma = 0;
  for (let i = 0; i < nome.length; i += 1) soma = (soma + nome.charCodeAt(i) * 7) % 997;
  return MATIZES[soma % MATIZES.length];
}

export function Avatar({ nome = "", tamanho = 32, className = "" }) {
  const h = matiz(nome);
  return (
    <span
      className={`avatar ${className}`}
      style={{
        width: tamanho,
        height: tamanho,
        fontSize: Math.max(10, Math.round(tamanho * 0.37)),
        "--avatar-fundo": `hsl(${h} 62% 92%)`,
        "--avatar-texto": `hsl(${h} 52% 32%)`,
        "--avatar-borda": `hsl(${h} 46% 82%)`,
      }}
      aria-hidden="true"
    >
      {iniciais(nome)}
    </span>
  );
}
