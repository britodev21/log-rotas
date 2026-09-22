import { useEffect, useState } from "react";

import { assinar, atualizar, instalar, situacao } from "../pwa/aplicativo";

/**
 * Estado do app instalado, para a tela: tem versão nova? dá para instalar?
 * está sem conexão?
 *
 * `online` vem do navegador, que só sabe se existe rede — não se a rede
 * chega no servidor. Serve para explicar o erro, nunca para decidir se vale
 * a pena tentar: quem decide isso é a chamada, tentando.
 */
export function useAplicativo() {
  const [estado, setEstado] = useState(situacao);
  const [online, setOnline] = useState(navigator.onLine);

  useEffect(() => assinar(setEstado), []);

  useEffect(() => {
    const ligou = () => setOnline(true);
    const caiu = () => setOnline(false);
    window.addEventListener("online", ligou);
    window.addEventListener("offline", caiu);
    return () => {
      window.removeEventListener("online", ligou);
      window.removeEventListener("offline", caiu);
    };
  }, []);

  return { ...estado, online, atualizar, instalar };
}
