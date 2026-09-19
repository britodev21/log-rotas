/**
 * Decodifica polyline codificada (precisao 5), o formato que o OSRM devolve.
 *
 * Sao poucas linhas e nenhuma dependencia: trazer uma biblioteca inteira
 * para isto seria peso sem retorno.
 */
export function decodificarPolyline(codificada, precisao = 5) {
  if (!codificada) return [];

  const fator = 10 ** precisao;
  const pontos = [];
  let indice = 0;
  let lat = 0;
  let lng = 0;

  while (indice < codificada.length) {
    let resultado = 1;
    let deslocamento = 0;
    let b;

    do {
      b = codificada.charCodeAt(indice++) - 63 - 1;
      resultado += b << deslocamento;
      deslocamento += 5;
    } while (b >= 0x1f);
    lat += resultado & 1 ? ~(resultado >> 1) : resultado >> 1;

    resultado = 1;
    deslocamento = 0;
    do {
      b = codificada.charCodeAt(indice++) - 63 - 1;
      resultado += b << deslocamento;
      deslocamento += 5;
    } while (b >= 0x1f);
    lng += resultado & 1 ? ~(resultado >> 1) : resultado >> 1;

    pontos.push([lat / fator, lng / fator]);
  }

  return pontos;
}
