/** Limpeza automática: prazos de guarda e últimas execuções. Só ADMIN. */

import { api } from "./client";

export const manutencao = {
  ler: () => api.get("/manutencao").then((r) => r.data),
  limpar: () => api.post("/manutencao/limpar").then((r) => r.data),
};
