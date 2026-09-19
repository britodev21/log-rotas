import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { ArrowRight, Building2, Lock, Mail, User } from "lucide-react";

import { consultarSetup, executarSetup } from "../api/auth";
import { mensagemDeErro } from "../api/client";
import {
  Alert,
  Button,
  InputField,
  Logo,
  Splash,
  ThemeToggle,
} from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { Vitrine } from "./Vitrine";
import "./auth.css";

const SENHA_MINIMA = 10;

/**
 * Primeiro acesso.
 *
 * Disponível apenas enquanto o sistema não tem nenhum usuário. Não é um
 * cadastro público: depois deste administrador, quem cria acesso é ele.
 */
export function Setup() {
  useDocumentTitle("Primeiro acesso");

  const { adotarSessao } = useAuth();
  const navegar = useNavigate();

  const [form, setForm] = useState({
    company_name: "Britto Móveis e Corrimão",
    admin_name: "",
    admin_email: "",
    admin_password: "",
    confirmacao: "",
  });
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  // null = ainda verificando se o sistema já foi configurado
  const [precisaConfigurar, setPrecisaConfigurar] = useState(null);

  useEffect(() => {
    let cancelado = false;
    consultarSetup()
      .then((d) => !cancelado && setPrecisaConfigurar(d.needs_setup))
      .catch((e) => {
        console.error("Falha ao consultar estado do sistema", e);
        if (!cancelado) setPrecisaConfigurar(false);
      });
    return () => {
      cancelado = true;
    };
  }, []);

  const alterar = (campo) => (evento) =>
    setForm((atual) => ({ ...atual, [campo]: evento.target.value }));

  const senhaCurta =
    form.admin_password.length > 0 && form.admin_password.length < SENHA_MINIMA;
  const senhasDiferem =
    form.confirmacao.length > 0 && form.admin_password !== form.confirmacao;

  async function aoEnviar(evento) {
    evento.preventDefault();
    setErro("");

    if (form.admin_password !== form.confirmacao) {
      setErro("As senhas não conferem.");
      return;
    }

    setEnviando(true);
    try {
      adotarSessao(
        await executarSetup({
          company_name: form.company_name,
          admin_name: form.admin_name,
          admin_email: form.admin_email,
          admin_password: form.admin_password,
        }),
      );
      navegar("/admin", { replace: true });
    } catch (e) {
      console.error("Falha no primeiro acesso", e);
      setErro(mensagemDeErro(e, "Não foi possível concluir a configuração."));
    } finally {
      setEnviando(false);
    }
  }

  if (precisaConfigurar === null) return <Splash mensagem="Verificando o sistema" />;
  if (precisaConfigurar === false) return <Navigate to="/entrar" replace />;

  return (
    <div className="entrada">
      <Vitrine />

      <main className="painel-entrada">
        <div className="painel-entrada__tema">
          <ThemeToggle />
        </div>

        <div className="painel-entrada__caixa painel-entrada__caixa--larga">
          <div className="painel-entrada__marca">
            <Logo tamanho={30} />
          </div>

          <h1 className="painel-entrada__titulo">Primeiro acesso</h1>
          <p className="painel-entrada__descricao">
            Vamos cadastrar a empresa e o seu administrador. Esta tela aparece
            uma única vez.
          </p>

          <form className="formulario" onSubmit={aoEnviar} noValidate>
            {erro && <Alert tom="erro">{erro}</Alert>}

            <div className="formulario__grupo">
              <span className="formulario__grupo-titulo">Empresa</span>
            </div>

            <InputField
              label="Nome da empresa"
              icone={Building2}
              value={form.company_name}
              onChange={alterar("company_name")}
              required
              obrigatorio
              autoFocus
            />

            <div className="formulario__grupo">
              <span className="formulario__grupo-titulo">Administrador</span>
            </div>

            <InputField
              label="Seu nome"
              icone={User}
              value={form.admin_name}
              onChange={alterar("admin_name")}
              autoComplete="name"
              required
              obrigatorio
            />

            <InputField
              label="E-mail"
              type="email"
              icone={Mail}
              value={form.admin_email}
              onChange={alterar("admin_email")}
              placeholder="voce@empresa.com.br"
              autoComplete="username"
              inputMode="email"
              required
              obrigatorio
            />

            <InputField
              label="Senha"
              type="password"
              icone={Lock}
              value={form.admin_password}
              onChange={alterar("admin_password")}
              autoComplete="new-password"
              ajuda={`Mínimo de ${SENHA_MINIMA} caracteres.`}
              erro={senhaCurta ? `Use ao menos ${SENHA_MINIMA} caracteres.` : ""}
              required
              obrigatorio
            />

            <InputField
              label="Confirme a senha"
              type="password"
              icone={Lock}
              value={form.confirmacao}
              onChange={alterar("confirmacao")}
              autoComplete="new-password"
              erro={senhasDiferem ? "As senhas não conferem." : ""}
              required
              obrigatorio
            />

            <Button
              type="submit"
              tamanho="lg"
              larguraTotal
              carregando={enviando}
              disabled={senhaCurta || senhasDiferem}
              iconeDireita={enviando ? undefined : ArrowRight}
            >
              {enviando ? "Criando acesso..." : "Criar acesso e entrar"}
            </Button>
          </form>

          <p className="painel-entrada__nota">
            O Log Rotas não tem cadastro público. Depois deste administrador,
            novos acessos são criados por ele dentro do sistema.
          </p>
        </div>
      </main>
    </div>
  );
}
