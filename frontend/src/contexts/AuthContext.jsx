/**
 * Estado de autenticacao da aplicacao.
 *
 * Guarda quem esta logado e expoe entrar/sair. Regra de negocio nao mora
 * aqui: o contexto so reflete o que o backend decidiu.
 */

import { createContext, useCallback, useEffect, useMemo, useState } from "react";

import { buscarPerfil, entrar as entrarApi, trocarSenha as trocarSenhaApi } from "../api/auth";
import { registrarPerdaDeSessao } from "../api/client";
import {
  gravarAvisoSenhaFraca,
  gravarSessao,
  lerAvisoSenhaFraca,
  lerSessao,
  limparSessao,
} from "../api/storage";

export const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [usuario, setUsuario] = useState(() => lerSessao().usuario);
  // Comeca carregando apenas se ha sessao guardada para validar.
  const [carregando, setCarregando] = useState(() => Boolean(lerSessao().accessToken));
  // A senha usada no login está numa lista de senhas conhecidas (ou leva o
  // nome da pessoa). Ela continua entrando, mas a tela pede a troca.
  const [senhaFraca, setSenhaFraca] = useState(lerAvisoSenhaFraca);

  const sair = useCallback(() => {
    limparSessao();
    setUsuario(null);
    setSenhaFraca(false);
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
      .catch((erro) => {
        if (cancelado) return;
        // Erro SEM resposta do servidor é falta de sinal, não sessão
        // inválida. Deslogar aqui tirava o motorista do aplicativo
        // justamente quando ele está sem rede na rua — e, com o app
        // instalado, era a tela de entrar que aparecia offline. Quem
        // invalida sessão é o 401 da API, tratado no cliente HTTP.
        if (!erro?.response) return;
        sair();
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
    setSenhaFraca(Boolean(dados.senha_fraca));
    gravarAvisoSenhaFraca(Boolean(dados.senha_fraca));
    return dados.user;
  }, []);

  /** Troca a própria senha. O servidor encerra as outras sessões e devolve
   *  tokens novos para esta — sem gravá-los, esta aba cairia junto. */
  const trocarSenha = useCallback(async (atual, nova) => {
    const tokens = await trocarSenhaApi(atual, nova);
    gravarSessao({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token });
    setSenhaFraca(false);
    gravarAvisoSenhaFraca(false);
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
      senhaFraca,
      trocarSenha,
    }),
    [usuario, carregando, entrar, adotarSessao, sair, senhaFraca, trocarSenha],
  );

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}
