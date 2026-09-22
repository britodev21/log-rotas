import { createHash } from "node:crypto";
import { readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { join, relative } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * Cabeçalhos de segurança da TELA em produção.
 *
 * A Content-Security-Policy diz ao navegador de onde a página pode carregar
 * código e recursos. É a proteção que mais importa aqui: o token de sessão
 * fica no localStorage (docs/LIMITACOES.md, 1.5), e uma CSP estrita impede
 * que um script injetado rode para roubá-lo.
 *
 * Só o que a tela usa de verdade, conferido no código:
 *   - fontes do Google (folha de estilo e arquivos de fonte);
 *   - ladrilhos do mapa da Esri (imagens);
 *   - a própria API, na mesma origem (/api, pelo proxy).
 * O link do Google Maps é navegação, não recurso carregado — não entra.
 *
 * Aplicados no `vite preview` (o build de produção servido localmente). No
 * `vite dev` não: o recarregamento a quente do React injeta script embutido
 * e seria bloqueado. Em produção, o nginx envia os mesmos cabeçalhos — ver
 * docs/SEGURANCA.md.
 */
/**
 * Gera o service worker a partir de `sw-modelo.js`, com a lista real do
 * build e uma versão tirada do conteúdo.
 *
 * Feito aqui, e não com uma biblioteca de PWA, porque o que precisa ser
 * automático é só isto: os nomes dos arquivos mudam a cada build (têm hash),
 * e uma lista escrita à mão ficaria velha em silêncio — o app abriria sem
 * sinal servindo o código do mês passado. As regras de cache continuam
 * legíveis em `sw-modelo.js`.
 */
function servicoWorker() {
  return {
    name: "log-rotas-service-worker",
    apply: "build",
    closeBundle() {
      const raiz = "dist";
      const arquivos = [];
      const varrer = (pasta) => {
        for (const nome of readdirSync(pasta)) {
          const caminho = join(pasta, nome);
          if (statSync(caminho).isDirectory()) varrer(caminho);
          else arquivos.push("/" + relative(raiz, caminho).split("\\").join("/"));
        }
      };
      varrer(raiz);

      // Fica de fora o que não faz falta sem sinal: os ícones grandes só
      // aparecem na instalação, e o mapa guarda os próprios ladrilhos.
      const precache = arquivos.filter(
        (a) => !a.startsWith("/icone-") && a !== "/apple-touch-icon.png",
      );
      const versao = createHash("sha256")
        .update(precache.join("|"))
        .digest("hex")
        .slice(0, 12);

      const modelo = readFileSync("sw-modelo.js", "utf8");
      writeFileSync(
        join(raiz, "sw.js"),
        modelo
          .replaceAll("__VERSAO__", versao)
          .replaceAll("__ARQUIVOS__", JSON.stringify(precache, null, 2)),
      );
    },
  };
}

export const CABECALHOS_PRODUCAO = {
  "Content-Security-Policy": [
    "default-src 'self'",
    "script-src 'self'",
    // O service worker é script da própria origem; o manifesto também.
    "worker-src 'self'",
    "manifest-src 'self'",
    "style-src 'self' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob: https://services.arcgisonline.com",
    // O service worker busca os ladrilhos e as fontes para guardar offline,
    // e busca de dentro do worker conta como connect-src — não como img-src.
    // Sem estes dois domínios aqui, o worker QUEBRA o que devia acelerar:
    // a imagem do mapa nem chega a ser baixada.
    "connect-src 'self' https://services.arcgisonline.com https://fonts.gstatic.com https://fonts.googleapis.com",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; "),
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "strict-origin-when-cross-origin",
  // GPS e tela acesa só para a própria página; câmera e microfone, ninguém.
  "Permissions-Policy": "geolocation=(self), screen-wake-lock=(self), camera=(), microphone=()",
};

export default defineConfig({
  plugins: [react(), servicoWorker()],
  build: {
    rollupOptions: {
      output: {
        // Separa o que quase nunca muda do codigo da aplicacao: o navegador
        // mantem react, router e leaflet em cache entre deploys, e so
        // rebaixa o pedaco que de fato mudou.
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          mapa: ["leaflet", "react-leaflet"],
        },
      },
    },
  },
  preview: {
    headers: CABECALHOS_PRODUCAO,
  },
  server: {
    port: 5173,
    // host: true expoe o dev server na rede local, necessario para testar a
    // interface do motorista em um celular de verdade.
    //
    // ATENCAO: navegador so libera navigator.geolocation em contexto seguro.
    // http://localhost conta como seguro, http://192.168.x.x NAO. Para testar
    // localizacao no celular sera preciso HTTPS (tunel ou certificado local).
    // Ver docs/LIMITACOES.md.
    host: true,
    proxy: {
      // Evita CORS no desenvolvimento: o frontend chama /api e o Vite
      // encaminha para o backend.
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
