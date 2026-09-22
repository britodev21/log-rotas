import { useEffect, useState } from "react";

/**
 * Mantém a tela do celular acesa enquanto `ativo`.
 *
 * Não é conforto: com a tela apagada, o navegador suspende a página e o GPS
 * dela para. Para o rastreamento funcionar numa página web, a tela precisa
 * ficar ligada — por isso o motorista é orientado a deixar o celular no
 * carregador durante a rota.
 *
 * O sistema operacional devolve a trava quando a página sai da frente
 * (troca de app, ligação). Ela é pedida de novo ao voltar.
 */
export function useTelaAcesa(ativo) {
  const suportado = typeof navigator !== "undefined" && "wakeLock" in navigator;
  const [acesa, setAcesa] = useState(false);

  useEffect(() => {
    if (!ativo || !suportado) return undefined;
    let trava = null;
    let vivo = true;

    const pedir = async () => {
      try {
        trava = await navigator.wakeLock.request("screen");
        if (!vivo) {
          trava.release();
          return;
        }
        setAcesa(true);
        trava.addEventListener("release", () => vivo && setAcesa(false));
      } catch {
        // Recusado (bateria fraca, economia de energia): a tela avisa.
        setAcesa(false);
      }
    };

    pedir();
    const aoVoltar = () => {
      if (document.visibilityState === "visible") pedir();
    };
    document.addEventListener("visibilitychange", aoVoltar);

    return () => {
      vivo = false;
      document.removeEventListener("visibilitychange", aoVoltar);
      trava?.release?.();
      setAcesa(false);
    };
  }, [ativo, suportado]);

  return { suportado, acesa };
}
