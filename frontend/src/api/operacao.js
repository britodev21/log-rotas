/** Chamadas de entregas, planejamento, painel e geocodificacao. */

import { api } from "./client";

// --- Entregas --------------------------------------------------------------
export const entregas = {
  listar: (filtros = {}) => api.get("/entregas", { params: filtros }).then((r) => r.data),
  obter: (id) => api.get(`/entregas/${id}`).then((r) => r.data),
  criar: (dados) => api.post("/entregas", dados).then((r) => r.data),
  alterar: (id, dados) => api.patch(`/entregas/${id}`, dados).then((r) => r.data),
  mudarStatus: (id, dados) =>
    api.post(`/entregas/${id}/status`, dados).then((r) => r.data),
  historico: (id) => api.get(`/entregas/${id}/historico`).then((r) => r.data),
  resumo: (data) => api.get("/entregas/resumo", { params: { data } }).then((r) => r.data),
};

// --- Planejamento ----------------------------------------------------------
export const planejamento = {
  listar: (filtros = {}) =>
    api.get("/planejamento", { params: filtros }).then((r) => r.data),
  obter: (id) => api.get(`/planejamento/${id}`).then((r) => r.data),
  // O calculo pode demorar: o solver tem limite proprio e o runner impoe
  // um teto maior. O timeout padrao de 20s do cliente nao serve aqui.
  calcular: (dados) =>
    api.post("/planejamento/calcular", dados, { timeout: 180000 }).then((r) => r.data),
  confirmar: (id, atribuicoes = {}) =>
    api.post(`/planejamento/${id}/confirmar`, { atribuicoes }).then((r) => r.data),
  descartar: (id) => api.post(`/planejamento/${id}/descartar`).then((r) => r.data),
};

// --- Painel ----------------------------------------------------------------
export const painel = {
  hoje: (data) => api.get("/painel", { params: { data } }).then((r) => r.data),
};

// --- Geocodificacao --------------------------------------------------------
export const geocodificacao = {
  pendentes: (filtros = {}) =>
    api.get("/geocodificacao/pendentes", { params: filtros }).then((r) => r.data),
  testar: (endereco) =>
    api.post("/geocodificacao/testar", null, { params: { endereco } }).then((r) => r.data),
  // Geocodificar respeita 1 requisicao por segundo no provedor: um lote de
  // 50 leva cerca de um minuto.
  umRegistro: (tipo, id, forcar = false) =>
    api
      .post(`/geocodificacao/${tipo}/${id}`, null, { params: { forcar }, timeout: 60000 })
      .then((r) => r.data),
  lote: (dados) =>
    api.post("/geocodificacao/lote", dados, { timeout: 300000 }).then((r) => r.data),
  definirCoordenada: (tipo, id, latitude, longitude) =>
    api
      .put(`/geocodificacao/${tipo}/${id}/coordenada`, { latitude, longitude })
      .then((r) => r.data),
};

// --- Motorista -------------------------------------------------------------
export const motorista = {
  rotas: (data) => api.get("/motorista/rotas", { params: { data } }).then((r) => r.data),
  rota: (id) => api.get(`/motorista/rotas/${id}`).then((r) => r.data),
  iniciar: (id) => api.post(`/motorista/rotas/${id}/iniciar`).then((r) => r.data),
  finalizar: (id) => api.post(`/motorista/rotas/${id}/finalizar`).then((r) => r.data),
  cheguei: (paradaId, coordenada = {}) =>
    api.post(`/motorista/paradas/${paradaId}/cheguei`, coordenada).then((r) => r.data),
  entregue: (itemId, dados) =>
    api.post(`/motorista/entregas/${itemId}/entregue`, dados).then((r) => r.data),
  naoEntregue: (itemId, dados) =>
    api.post(`/motorista/entregas/${itemId}/nao-entregue`, dados).then((r) => r.data),
};
