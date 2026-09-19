import { useEffect, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Eye, EyeOff, Lock, Mail } from "lucide-react";

import { consultarSetup } from "../api/auth";
import { mensagemDeErro } from "../api/client";
import { Alert, Button, InputField, Logo, ThemeToggle } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { Vitrine } from "./Vitrine";
import "./auth.css";

export function Login() {
  useDocumentTitle("Entrar");

  const { entrar, autenticado, usuario } = useAuth();
  const navegar = useNavigate();
  const local = useLocation();

  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [verSenha, setVerSenha] = useState(false);
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [precisaConfigurar, setPrecisaConfigurar] = useState(false);

  // Com o sistema vazio não existe ninguém para entrar: leva direto ao
  // primeiro acesso, em vez de mostrar um login impossível de usar.
  useEffect(() => {
    let cancelado = false;
    consultarSetup()
      .then((d) => !cancelado && setPrecisaConfigurar(d.needs_setup))
      .catch((e) => console.error("Falha ao consultar estado do sistema", e));
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
      console.error("Falha no login", e);
      setErro(mensagemDeErro(e, "Não foi possível entrar."));
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
      <Vitrine />

      <main className="painel-entrada">
        <div className="painel-entrada__tema">
          <ThemeToggle />
        </div>

        <div className="painel-entrada__caixa">
          <div className="painel-entrada__marca">
            <Logo tamanho={30} />
          </div>

          <h1 className="painel-entrada__titulo">Entrar</h1>
          <p className="painel-entrada__descricao">
            Acesse o painel da operação.
          </p>

          <form className="formulario" onSubmit={aoEnviar} noValidate>
            {erro && <Alert tom="erro">{erro}</Alert>}

            <InputField
              label="E-mail"
              type="email"
              name="email"
              icone={Mail}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="voce@empresa.com.br"
              autoComplete="username"
              inputMode="email"
              autoFocus
              required
              obrigatorio
            />

            <InputField
              label="Senha"
              type={verSenha ? "text" : "password"}
              name="senha"
              icone={Lock}
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              autoComplete="current-password"
              required
              obrigatorio
              aDireita={
                <Button
                  variante="sutil"
                  tamanho="sm"
                  icone={verSenha ? EyeOff : Eye}
                  onClick={() => setVerSenha((v) => !v)}
                  aria-label={verSenha ? "Ocultar senha" : "Mostrar senha"}
                  tabIndex={-1}
                />
              }
            />

            <Button
              type="submit"
              tamanho="lg"
              larguraTotal
              carregando={enviando}
              iconeDireita={enviando ? undefined : ArrowRight}
            >
              {enviando ? "Entrando..." : "Entrar"}
            </Button>
          </form>

          <p className="painel-entrada__nota">
            Esqueceu a senha? Peça a um administrador para redefinir — por
            segurança, ninguém além dele consegue fazer isso.
          </p>
        </div>
      </main>
    </div>
  );
}
