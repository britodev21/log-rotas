/** Chamadas de gestao de usuarios (somente ADMIN). */

import { api } from "./client";

export const listarUsuarios = (filtros = {}) =>
  api.get("/usuarios", { params: filtros }).then((r) => r.data);

export const criarUsuario = (dados) => api.post("/usuarios", dados).then((r) => r.data);

export const alterarUsuario = (id, dados) =>
  api.patch(`/usuarios/${id}`, dados).then((r) => r.data);

export const redefinirSenha = (id, novaSenha) =>
  api.post(`/usuarios/${id}/senha`, { new_password: novaSenha }).then((r) => r.data);
