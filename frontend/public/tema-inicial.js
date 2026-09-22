// Carregado em arquivo, e nao embutido no index.html, por causa da
// Content-Security-Policy: com script-src 'self', script embutido e
// bloqueado. Continua sincrono no <head>, entao roda antes do primeiro
// pixel do mesmo jeito.
// Aplica o tema antes do primeiro pixel ser pintado. Sem isso, a tela
// pisca claro antes do React montar e trocar para escuro — o defeito
// mais visível que um tema escuro pode ter.
(function () {
  try {
    var salvo = localStorage.getItem("logrotas.tema");
    var tema =
      salvo ||
      (window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "escuro"
        : "claro");
    document.documentElement.setAttribute("data-tema", tema);
  } catch (e) {
    document.documentElement.setAttribute("data-tema", "claro");
  }
})();
