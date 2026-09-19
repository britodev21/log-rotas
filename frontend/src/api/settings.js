/** Chamadas da configuracao da empresa (somente ADMIN). */

import { api } from "./client";

export const buscarConfiguracoes = () => api.get("/configuracoes").then((r) => r.data);

export const salvarConfiguracoes = (dados) =>
  api.patch("/configuracoes", dados).then((r) => r.data);
