import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { consultarSetup } from "../api/auth";
import { mensagemDeErro } from "../api/client";
import { Alert, Button, InputField } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import "./auth.css";

export function Login() {
  useDocumentTitle("Entrar");

  const { entrar, autenticado, usuario } = useAuth();
  const navegar = useNavigate();
  const local = useLocation();

  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [precisaConfigurar, setPrecisaConfigurar] = useState(false);

  // Com o sistema vazio nao existe ninguem para entrar: leva direto ao
  // primeiro acesso em vez de mostrar um login impossivel de usar.
  useEffect(() => {
    let cancelado = false;
    consultarSetup()
      .then((d) => !cancelado && setPrecisaConfigurar(d.needs_setup))
      .catch(() => undefined);
    return () => {
      cancelado = true;
    };
  }, []);

  async function aoEnviar(evento) {
    evento.preventDefault();
    setErro("");
    setEnviando(true);
    try {
      const perfil = await entrar(email, senha);
      const destino =
        local.state?.de ?? (perfil.role === "ADMIN" ? "/admin" : "/motorista");
      navegar(destino, { replace: true });
    } catch (e) {
      setErro(mensagemDeErro(e, "Nao foi possivel entrar."));
    } finally {
      setEnviando(false);
    }
  }

  if (autenticado) {
    return <Navigate to={usuario.role === "ADMIN" ? "/admin" : "/motorista"} replace />;
  }
  if (precisaConfigurar) {
    return <Navigate to="/primeiro-acesso" replace />;
  }

  return (
    <div className="entrada">
      <div className="entrada__caixa">
        <p className="entrada__marca">Log Rotas</p>
        <p className="entrada__subtitulo">Britto Moveis e Corrimao</p>

        <form className="entrada__formulario" onSubmit={aoEnviar} noValidate>
          {erro && <Alert tom="erro">{erro}</Alert>}

          <InputField
            label="E-mail"
            type="email"
            name="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            inputMode="email"
            autoFocus
            required
            obrigatorio
          />

          <InputField
            label="Senha"
            type="password"
            name="senha"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            autoComplete="current-password"
            required
            obrigatorio
          />

          <Button type="submit" carregando={enviando} larguraTotal tamanho="grande">
            Entrar
          </Button>
        </form>

        <p className="entrada__rodape">
          Esqueceu a senha? Peca a um administrador para redefinir.
        </p>
      </div>
    </div>
  );
}
