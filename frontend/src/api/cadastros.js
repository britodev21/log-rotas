/** Chamadas dos cadastros (somente ADMIN). */

import { api } from "./client";

/**
 * Os quatro cadastros expoem exatamente a mesma interface. Gerar os modulos
 * a partir do prefixo evita quatro arquivos identicos que divergiriam com o
 * tempo — e deixa obvio que qualquer diferenca de comportamento entre eles
 * seria acidental.
 */
function recurso(prefixo) {
  return {
    listar: (filtros = {}) =>
      api.get(prefixo, { params: filtros }).then((r) => r.data),
    obter: (id) => api.get(`${prefixo}/${id}`).then((r) => r.data),
    criar: (dados) => api.post(prefixo, dados).then((r) => r.data),
    alterar: (id, dados) => api.patch(`${prefixo}/${id}`, dados).then((r) => r.data),
  };
}

export const bases = recurso("/bases");
export const veiculos = recurso("/veiculos");
export const motoristas = recurso("/motoristas");
export const clientes = recurso("/clientes");
