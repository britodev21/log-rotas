import { createContext, useCallback, useMemo, useRef, useState } from "react";

import { ToastViewport } from "../components/ui/Toast";

export const ToastContext = createContext(null);

const DURACAO_PADRAO = 4500;

/**
 * Sistema de notificações.
 *
 * Substitui o aviso empilhado no topo da página, que sai do campo de visão
 * assim que a pessoa rola a tela — exatamente quando ela acabou de agir e
 * mais precisa da confirmação.
 *
 * Erro não some sozinho: exige leitura e, quase sempre, uma decisão.
 */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const temporizadores = useRef(new Map());

  const remover = useCallback((id) => {
    const temporizador = temporizadores.current.get(id);
    if (temporizador) {
      clearTimeout(temporizador);
      temporizadores.current.delete(id);
    }
    setToasts((atuais) => atuais.filter((t) => t.id !== id));
  }, []);

  const mostrar = useCallback(
    ({ tom = "info", titulo, mensagem, duracao }) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      // Erro fica até ser dispensado; o resto se apaga sozinho.
      const tempo = duracao ?? (tom === "erro" ? null : DURACAO_PADRAO);

      setToasts((atuais) => {
        const proximos = [...atuais, { id, tom, titulo, mensagem }];
        // No máximo três na tela: além disso a pilha vira parede e nenhuma
        // das mensagens é lida.
        return proximos.slice(-3);
      });

      if (tempo) {
        temporizadores.current.set(
          id,
          setTimeout(() => remover(id), tempo),
        );
      }
      return id;
    },
    [remover],
  );

  const api = useMemo(
    () => ({
      mostrar,
      remover,
      sucesso: (titulo, mensagem) => mostrar({ tom: "sucesso", titulo, mensagem }),
      erro: (titulo, mensagem) => mostrar({ tom: "erro", titulo, mensagem }),
      info: (titulo, mensagem) => mostrar({ tom: "info", titulo, mensagem }),
      atencao: (titulo, mensagem) => mostrar({ tom: "atencao", titulo, mensagem }),
    }),
    [mostrar, remover],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastViewport toasts={toasts} aoFechar={remover} />
    </ToastContext.Provider>
  );
}
