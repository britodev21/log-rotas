/**
 * Guarda a sessao no navegador.
 *
 * Decisao consciente: os tokens ficam em localStorage, o que os expoe a XSS.
 * A alternativa (cookie httpOnly) dificultaria o aplicativo nativo previsto
 * mais adiante. As defesas escolhidas sao access token curto (60 min),
 * revogacao por token_version no backend e nenhum HTML injetado sem escape.
 * Ver docs/LIMITACOES.md.
 */

const CHAVE_ACCESS = "logrotas.access";
const CHAVE_REFRESH = "logrotas.refresh";
const CHAVE_USUARIO = "logrotas.usuario";

export function lerSessao() {
  try {
    const usuario = localStorage.getItem(CHAVE_USUARIO);
    return {
      accessToken: localStorage.getItem(CHAVE_ACCESS),
      refreshToken: localStorage.getItem(CHAVE_REFRESH),
      usuario: usuario ? JSON.parse(usuario) : null,
    };
  } catch {
    // Modo anonimo ou armazenamento bloqueado: a aplicacao continua
    // funcionando, apenas sem lembrar da sessao.
    return { accessToken: null, refreshToken: null, usuario: null };
  }
}

export function gravarSessao({ accessToken, refreshToken, usuario }) {
  try {
    if (accessToken) localStorage.setItem(CHAVE_ACCESS, accessToken);
    if (refreshToken) localStorage.setItem(CHAVE_REFRESH, refreshToken);
    if (usuario) localStorage.setItem(CHAVE_USUARIO, JSON.stringify(usuario));
  } catch {
    /* sem persistencia: a sessao vale apenas enquanto a aba estiver aberta */
  }
}

export function limparSessao() {
  try {
    [CHAVE_ACCESS, CHAVE_REFRESH, CHAVE_USUARIO].forEach((c) =>
      localStorage.removeItem(c),
    );
  } catch {
    /* nada a limpar */
  }
}

export function lerAccessToken() {
  try {
    return localStorage.getItem(CHAVE_ACCESS);
  } catch {
    return null;
  }
}

export function lerRefreshToken() {
  try {
    return localStorage.getItem(CHAVE_REFRESH);
  } catch {
    return null;
  }
}
