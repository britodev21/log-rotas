/** Segurança: política em vigor, contas bloqueadas e eventos. Só ADMIN. */

import { api } from "./client";

export const seguranca = {
  politica: () => api.get("/seguranca/politica").then((r) => r.data),
  bloqueios: () => api.get("/seguranca/bloqueios").then((r) => r.data),
  desbloquear: (email) =>
    api.post("/seguranca/bloqueios/desbloquear", { email }).then((r) => r.data),
  eventos: (limite = 100) =>
    api.get("/seguranca/eventos", { params: { limite } }).then((r) => r.data),
};
