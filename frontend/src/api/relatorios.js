/** Relatórios do período e a exportação em CSV. Só ADMIN. */

import { api } from "./client";

export const relatorios = {
  periodo: (params) => api.get("/relatorios", { params }).then((r) => r.data),

  /**
   * Baixa o CSV pelo próprio cliente HTTP, e não por um link direto.
   *
   * O arquivo exige o token no cabeçalho; um `<a href>` comum iria sem ele e
   * voltaria 401. Então o conteúdo vem por XHR e o download é disparado com
   * uma URL de objeto, que o navegador salva com o nome que o servidor mandou.
   */
  baixarCsv: async (params) => {
    const resposta = await api.get("/relatorios/entregas.csv", {
      params,
      responseType: "blob",
    });
    const nome =
      /filename="([^"]+)"/.exec(resposta.headers["content-disposition"] ?? "")?.[1] ??
      "entregas.csv";
    const url = URL.createObjectURL(resposta.data);
    const link = document.createElement("a");
    link.href = url;
    link.download = nome;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    return nome;
  },
};
