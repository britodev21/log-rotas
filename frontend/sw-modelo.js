/**
 * Service worker do Log Rotas — o que faz o site abrir sem sinal.
 *
 * Este arquivo é um MODELO: o build preenche a versão e a lista de
 * arquivos do `dist` nas duas constantes abaixo (ver `vite.config.js`).
 * Escrito à
 * mão, e não gerado por biblioteca, porque são três regras e cada uma
 * precisa ser defensável:
 *
 * 1. **Tela (navegação): rede primeiro, cache como rede de segurança.**
 *    Sem sinal, o app abre com a última versão guardada em vez da página de
 *    dinossauro. Com sinal, sempre a versão do servidor.
 * 2. **Arquivos do build: cache primeiro.** Eles têm hash no nome; um nome
 *    novo é um arquivo novo, então o guardado nunca fica velho.
 * 3. **Ladrilhos do mapa: cache primeiro, com teto.** É o que mais adianta
 *    na rua: a região que o motorista já abriu continua desenhando sem
 *    sinal. Teto de LIMITE_MAPA ladrilhos para não encher o aparelho.
 *
 * O QUE ESTE SERVICE WORKER **NÃO** FAZ, de propósito:
 *
 * - **Não guarda resposta da API.** Rota, entrega e posição são dados de
 *   operação: mostrar a lista de ontem como se fosse a de hoje é pior do
 *   que dizer "sem conexão".
 * - **Não guarda registro feito sem sinal.** "Cheguei" e "entregue" exigem
 *   conexão; o app mostra o erro. Fila offline precisa de banco no
 *   aparelho e reenvio ordenado — está descrito em docs/LIMITACOES.md.
 *
 * Atualização: o worker novo espera, o app avisa na tela, e só assume
 * quando a pessoa aceita. Trocar o código embaixo de um motorista no meio
 * de uma entrega é como reiniciar o caminhão no farol.
 */

const VERSAO = "__VERSAO__";
const ARQUIVOS = __ARQUIVOS__;

const CACHE_APP = `logrotas-app-${VERSAO}`;
const CACHE_MAPA = "logrotas-mapa";
const CACHE_FONTES = "logrotas-fontes";
const LIMITE_MAPA = 300;

const MAPA = "https://services.arcgisonline.com/";
const FONTES = ["https://fonts.googleapis.com/", "https://fonts.gstatic.com/"];

self.addEventListener("install", (evento) => {
  evento.waitUntil(
    caches.open(CACHE_APP).then((cache) => cache.addAll(ARQUIVOS)),
  );
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(
    (async () => {
      const nomes = await caches.keys();
      await Promise.all(
        nomes
          .filter((n) => n.startsWith("logrotas-app-") && n !== CACHE_APP)
          .map((n) => caches.delete(n)),
      );
      await self.clients.claim();
    })(),
  );
});

/** A tela pede para assumir quando a pessoa aceita a atualização. */
self.addEventListener("message", (evento) => {
  if (evento.data === "assumir") self.skipWaiting();
});

async function comTeto(cache, limite) {
  const chaves = await cache.keys();
  if (chaves.length <= limite) return;
  // Sai o mais antigo: a região que o motorista abriu por último é a que
  // ele ainda vai precisar.
  await Promise.all(chaves.slice(0, chaves.length - limite).map((c) => cache.delete(c)));
}

async function cachePrimeiro(requisicao, nomeDoCache, limite) {
  const cache = await caches.open(nomeDoCache);
  const guardado = await cache.match(requisicao);
  if (guardado) return guardado;
  const resposta = await fetch(requisicao);
  // Resposta opaca (ladrilho de outro domínio) não diz o status; guardar
  // mesmo assim é o que permite o mapa funcionar sem sinal.
  if (resposta.ok || resposta.type === "opaque") {
    await cache.put(requisicao, resposta.clone());
    if (limite) await comTeto(cache, limite);
  }
  return resposta;
}

async function redePrimeiro(requisicao) {
  try {
    return await fetch(requisicao);
  } catch (erro) {
    const cache = await caches.open(CACHE_APP);
    const guardado = await cache.match("/index.html");
    if (guardado) return guardado;
    throw erro;
  }
}

self.addEventListener("fetch", (evento) => {
  const { request } = evento;
  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Dado de operação nunca vem do cache.
  if (url.origin === self.location.origin && url.pathname.startsWith("/api/")) return;

  if (request.mode === "navigate") {
    evento.respondWith(redePrimeiro(request));
    return;
  }

  if (url.origin === self.location.origin && url.pathname.startsWith("/assets/")) {
    evento.respondWith(cachePrimeiro(request, CACHE_APP));
    return;
  }

  if (request.url.startsWith(MAPA)) {
    evento.respondWith(cachePrimeiro(request, CACHE_MAPA, LIMITE_MAPA));
    return;
  }

  if (FONTES.some((f) => request.url.startsWith(f))) {
    evento.respondWith(cachePrimeiro(request, CACHE_FONTES));
  }
});
