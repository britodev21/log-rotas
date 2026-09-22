/**
 * Cliente HTTP unico da aplicacao.
 *
 * Nenhum componente React chama axios diretamente: tudo passa por aqui, que
 * e onde ficam o token, a renovacao de sessao e a traducao de erro. Assim a
 * tela cuida de tela, nao de protocolo.
 */

import axios from "axios";
import { gravarSessao, lerAccessToken, lerRefreshToken, limparSessao } from "./storage";

export const api = axios.create({
  baseURL: "/api/v1",
  timeout: 20000,
  headers: { "Content-Type": "application/json" },
  // Lista vai como `status=A&status=B`, que e o que o FastAPI le. O padrao
  // do axios, `status[]=A`, era ignorado em silencio: o planejador listava
  // TODAS as entregas do dia, inclusive as ja planejadas, e o calculo
  // voltava 409.
  paramsSerializer: { indexes: null },
});

api.interceptors.request.use((config) => {
  const token = lerAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

/** Chamado quando a sessao acaba de vez — definido pelo AuthContext. */
let aoPerderSessao = () => {};
export function registrarPerdaDeSessao(callback) {
  aoPerderSessao = callback;
}

// Uma renovacao por vez: varias chamadas que recebem 401 juntas esperam a
// mesma promessa, em vez de disparar N refreshes concorrentes.
let renovacaoEmCurso = null;

async function renovarSessao() {
  const refreshToken = lerRefreshToken();
  if (!refreshToken) throw new Error("sem refresh token");

  if (!renovacaoEmCurso) {
    renovacaoEmCurso = axios
      .post("/api/v1/auth/refresh", { refresh_token: refreshToken })
      .then(({ data }) => {
        gravarSessao({
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
        });
        return data.access_token;
      })
      .finally(() => {
        renovacaoEmCurso = null;
      });
  }
  return renovacaoEmCurso;
}

api.interceptors.response.use(
  (resposta) => resposta,
  async (erro) => {
    const requisicao = erro.config;
    const status = erro.response?.status;

    const podeRenovar =
      status === 401 &&
      requisicao &&
      !requisicao._tentouRenovar &&
      !requisicao.url?.includes("/auth/login") &&
      !requisicao.url?.includes("/auth/refresh");

    if (podeRenovar) {
      requisicao._tentouRenovar = true;
      try {
        const token = await renovarSessao();
        requisicao.headers.Authorization = `Bearer ${token}`;
        return api(requisicao);
      } catch {
        limparSessao();
        aoPerderSessao();
      }
    }

    return Promise.reject(erro);
  },
);

/**
 * Extrai a mensagem que o usuario deve ler.
 *
 * O backend responde {erro, mensagem, detalhes} nos erros de dominio e o
 * formato do FastAPI nos erros de validacao. Aqui os dois viram texto.
 */
export function mensagemDeErro(erro, alternativa = "Nao foi possivel concluir a operacao.") {
  const dados = erro?.response?.data;
  if (!dados) {
    if (erro?.code === "ECONNABORTED") return "O servidor demorou demais para responder.";
    if (!erro?.response) return "Sem conexao com o servidor.";
    return alternativa;
  }
  if (typeof dados.mensagem === "string") return dados.mensagem;
  if (Array.isArray(dados.detail)) {
    const primeiro = dados.detail[0];
    if (primeiro?.msg) return primeiro.msg;
  }
  if (typeof dados.detail === "string") return dados.detail;
  return alternativa;
}
