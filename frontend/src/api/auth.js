/** Chamadas de autenticacao e primeiro acesso. */

import { api } from "./client";

export const consultarSetup = () => api.get("/setup/status").then((r) => r.data);

export const executarSetup = (dados) => api.post("/setup", dados).then((r) => r.data);

export const entrar = (email, senha) =>
  api.post("/auth/login", { email, password: senha }).then((r) => r.data);

export const buscarPerfil = () => api.get("/auth/me").then((r) => r.data);

export const trocarSenha = (senhaAtual, novaSenha) =>
  api
    .post("/auth/senha", { current_password: senhaAtual, new_password: novaSenha })
    .then((r) => r.data);
