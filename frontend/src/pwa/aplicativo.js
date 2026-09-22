/**
 * O app instalado: registro do service worker, atualização e instalação.
 *
 * Um módulo só, com assinantes, e não um hook por tela, porque os dois
 * eventos que importam chegam UMA vez e cedo — antes de qualquer tela
 * montar. Quem monta depois pergunta o estado atual em vez de perder o
 * evento.
 */

const PRODUCAO = import.meta.env.PROD;

let registro = null;
let esperando = null; // service worker novo, pronto, aguardando permissão
let pedidoDeInstalacao = null; // evento do navegador que abre o "instalar"
let instalado = false;

const assinantes = new Set();

function avisar() {
  const estado = situacao();
  assinantes.forEach((f) => f(estado));
}

export function situacao() {
  return {
    temAtualizacao: Boolean(esperando),
    podeInstalar: Boolean(pedidoDeInstalacao) && !instalado,
    instalado: instalado || jaEstaInstalado(),
  };
}

export function assinar(callback) {
  assinantes.add(callback);
  return () => assinantes.delete(callback);
}

/** Aberto pela tela inicial do celular, e não pelo navegador. */
export function jaEstaInstalado() {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    window.navigator.standalone === true
  );
}

/**
 * Registra o service worker e observa versões novas.
 *
 * Só em produção: no desenvolvimento, um worker guardando arquivos
 * atrapalha o recarregamento a quente e faz depurar virar adivinhação.
 */
export function iniciar() {
  window.addEventListener("beforeinstallprompt", (evento) => {
    // Sem isto o Chrome mostra a própria barra, na hora que ele decide. O
    // convite fica na tela do motorista, onde faz sentido.
    evento.preventDefault();
    pedidoDeInstalacao = evento;
    avisar();
  });

  window.addEventListener("appinstalled", () => {
    instalado = true;
    pedidoDeInstalacao = null;
    avisar();
  });

  if (!PRODUCAO || !("serviceWorker" in navigator)) return;

  window.addEventListener("load", async () => {
    try {
      registro = await navigator.serviceWorker.register("/sw.js");

      if (registro.waiting && navigator.serviceWorker.controller) {
        esperando = registro.waiting;
        avisar();
      }

      registro.addEventListener("updatefound", () => {
        const novo = registro.installing;
        if (!novo) return;
        novo.addEventListener("statechange", () => {
          // Sem controlador é a primeira visita: não há o que "atualizar".
          if (novo.state === "installed" && navigator.serviceWorker.controller) {
            esperando = novo;
            avisar();
          }
        });
      });

      // O worker novo assumiu: a tela recarrega uma vez para passar a rodar
      // o código dele por inteiro.
      let recarregando = false;
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        if (recarregando) return;
        recarregando = true;
        window.location.reload();
      });
    } catch (erro) {
      // App sem service worker continua funcionando; só não abre sem sinal.
      console.error("Não foi possível registrar o service worker", erro);
    }
  });
}

/** A pessoa aceitou a atualização. */
export function atualizar() {
  if (!esperando) return;
  esperando.postMessage("assumir");
  esperando = null;
  avisar();
}

/** Abre o convite de instalação do navegador. Devolve o que a pessoa disse. */
export async function instalar() {
  if (!pedidoDeInstalacao) return "indisponivel";
  pedidoDeInstalacao.prompt();
  const { outcome } = await pedidoDeInstalacao.userChoice;
  pedidoDeInstalacao = null;
  avisar();
  return outcome;
}
