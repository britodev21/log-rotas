import { useCallback, useEffect, useState } from "react";

/**
 * Controla quando o tutorial guiado aparece.
 *
 * Abre sozinho na primeira vez e nunca mais — quem já sabe usar não precisa
 * fechar o mesmo aviso toda manhã. Fica guardado por perfil e por versão do
 * roteiro: mudando o tutorial, ele volta a aparecer uma vez.
 *
 * O registro é local, no aparelho. Trocar de celular mostra o tutorial de
 * novo, e isso é melhor do que o contrário: quem pegou um aparelho novo é
 * justamente quem pode precisar dele.
 */
const VERSAO = "v1";
const ESPERA_MS = 900;

export function useTutorial(perfil) {
  const chave = `logrotas.tutorial.${perfil}.${VERSAO}`;
  const [aberto, setAberto] = useState(false);

  useEffect(() => {
    let visto = true;
    try {
      visto = localStorage.getItem(chave) === "1";
    } catch {
      // Sem armazenamento: não insiste, para não abrir a cada tela.
      visto = true;
    }
    if (visto) return undefined;
    // Espera a tela montar: destacar um botão que ainda não existe mostraria
    // o tutorial no lugar errado.
    const t = setTimeout(() => setAberto(true), ESPERA_MS);
    return () => clearTimeout(t);
  }, [chave]);

  const fechar = useCallback(() => {
    setAberto(false);
    try {
      localStorage.setItem(chave, "1");
    } catch {
      // Sem armazenamento, o tutorial volta na próxima visita.
    }
  }, [chave]);

  const iniciar = useCallback(() => setAberto(true), []);

  return { aberto, iniciar, fechar };
}
