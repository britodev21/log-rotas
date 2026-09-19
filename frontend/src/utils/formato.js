/** Formatacao de numeros operacionais.
 *
 * Regra do projeto: valor ausente NAO vira zero. Zero significa "medimos e
 * deu zero"; ausencia significa "nao sabemos". Trocar um pelo outro faz a
 * equipe confiar num numero que nunca existiu.
 */

const SEM_DADO = "—";

export function distancia(metros) {
  if (metros === null || metros === undefined) return SEM_DADO;
  if (metros < 1000) return `${Math.round(metros)} m`;
  return `${(metros / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} km`;
}

export function duracao(segundos) {
  if (segundos === null || segundos === undefined) return SEM_DADO;
  const horas = Math.floor(segundos / 3600);
  const minutos = Math.round((segundos % 3600) / 60);
  if (horas === 0) return `${minutos} min`;
  return minutos === 0 ? `${horas}h` : `${horas}h${String(minutos).padStart(2, "0")}`;
}

export function peso(kg) {
  if (kg === null || kg === undefined) return SEM_DADO;
  return `${Number(kg).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} kg`;
}

export function hora(iso) {
  if (!iso) return SEM_DADO;
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

export function dataHora(iso) {
  if (!iso) return SEM_DADO;
  return new Date(iso).toLocaleString("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function dataCurta(iso) {
  if (!iso) return SEM_DADO;
  const [ano, mes, dia] = iso.slice(0, 10).split("-");
  return `${dia}/${mes}/${ano}`;
}

export function hoje() {
  // Data LOCAL, nao UTC: toISOString() converte para UTC e, a noite no
  // Brasil, devolveria a data de amanha.
  const d = new Date();
  const mes = String(d.getMonth() + 1).padStart(2, "0");
  const dia = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mes}-${dia}`;
}

export function telefone(digitos) {
  if (!digitos) return SEM_DADO;
  const n = String(digitos);
  if (n.length === 11) return `(${n.slice(0, 2)}) ${n.slice(2, 7)}-${n.slice(7)}`;
  if (n.length === 10) return `(${n.slice(0, 2)}) ${n.slice(2, 6)}-${n.slice(6)}`;
  return n;
}

export const PRIORIDADES = {
  URGENTE: { rotulo: "Urgente", tom: "perigo" },
  ALTA: { rotulo: "Alta", tom: "atencao" },
  NORMAL: { rotulo: "Normal", tom: "neutro" },
  BAIXA: { rotulo: "Baixa", tom: "neutro" },
};

export const MOTIVOS_INSUCESSO = [
  { valor: "CLIENTE_AUSENTE", rotulo: "Cliente ausente" },
  { valor: "ENDERECO_INCORRETO", rotulo: "Endereço incorreto" },
  { valor: "RECUSA", rotulo: "Cliente recusou" },
  { valor: "ESTABELECIMENTO_FECHADO", rotulo: "Estabelecimento fechado" },
  { valor: "PROBLEMA_ACESSO", rotulo: "Problema de acesso" },
  { valor: "AVARIA", rotulo: "Produto avariado" },
  { valor: "FALTA_PRODUTO", rotulo: "Produto não embarcado" },
  { valor: "OUTRO", rotulo: "Outro" },
];
