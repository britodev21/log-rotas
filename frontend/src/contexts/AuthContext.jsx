/**
 * Estado de autenticacao da aplicacao.
 *
 * Guarda quem esta logado e expoe entrar/sair. Regra de negocio nao mora
 * aqui: o contexto so reflete o que o backend decidiu.
 */

import { createContext, useCallback, useEffect, useMemo, useState } from "react";

import { buscarPerfil, entrar as entrarApi } from "../api/auth";
import { registrarPerdaDeSessao } from "../api/client";
import { gravarSessao, lerSessao, limparSessao } from "../api/storage";

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(() => lerSessao().usuario);
  // Comeca carregando apenas se ha sessao guardada para validar.
  const [carregando, setCarregando] = useState(() => Boolean(lerSessao().accessToken));

  const sair = useCallback(() => {
    limparSessao();
    setUsuario(null);
  }, []);

  // O cliente HTTP avisa aqui quando a renovacao de sessao falha.
  useEffect(() => {
    registrarPerdaDeSessao(() => setUsuario(null));
  }, []);

  // Na abertura da aplicacao, confirma com o backend que a sessao guardada
  // ainda vale. Sem isso, um usuario desativado continuaria vendo a interface
  // ate a primeira chamada falhar.
  useEffect(() => {
    const { accessToken } = lerSessao();
    if (!accessToken) return;

    let cancelado = false;
    buscarPerfil()
      .then((perfil) => {
        if (cancelado) return;
        setUsuario(perfil);
        gravarSessao({ usuario: perfil });
      })
      .catch(() => {
        if (!cancelado) sair();
      })
      .finally(() => {
        if (!cancelado) setCarregando(false);
      });

    return () => {
      cancelado = true;
    };
  }, [sair]);

  const entrar = useCallback(async (email, senha) => {
    const dados = await entrarApi(email, senha);
    gravarSessao({
      accessToken: dados.access_token,
      refreshToken: dados.refresh_token,
      usuario: dados.user,
    });
    setUsuario(dados.user);
    return dados.user;
  }, []);

  /** Usado pelo primeiro acesso, que ja devolve a sessao pronta. */
  const adotarSessao = useCallback((dados) => {
    gravarSessao({
      accessToken: dados.access_token,
      refreshToken: dados.refresh_token,
      usuario: dados.user,
    });
    setUsuario(dados.user);
    return dados.user;
  }, []);

  const valor = useMemo(
    () => ({
      usuario,
      carregando,
      autenticado: Boolean(usuario),
      ehAdmin: usuario?.role === "ADMIN",
      ehMotorista: usuario?.role === "MOTORISTA",
      entrar,
      adotarSessao,
      sair,
    }),
    [usuario, carregando, entrar, adotarSessao, sair],
  );

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}
