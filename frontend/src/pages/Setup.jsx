import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { consultarSetup, executarSetup } from "../api/auth";
import { mensagemDeErro } from "../api/client";
import { Alert, Button, InputField } from "../components/ui";
import { useAuth } from "../hooks/useAuth";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import "./auth.css";

const SENHA_MINIMA = 10;

/**
 * Primeiro acesso.
 *
 * Disponivel apenas enquanto o sistema nao tem nenhum usuario. Nao e um
 * cadastro publico: depois deste administrador, quem cria acesso e ele.
 */
export function Setup() {
  useDocumentTitle("Primeiro acesso");

  const { adotarSessao } = useAuth();
  const navegar = useNavigate();

  const [form, setForm] = useState({
    company_name: "Britto Moveis e Corrimao",
    admin_name: "",
    admin_email: "",
    admin_password: "",
    confirmacao: "",
  });
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  // null = ainda verificando se o sistema ja foi configurado
  const [precisaConfigurar, setPrecisaConfigurar] = useState(null);

  useEffect(() => {
    let cancelado = false;
    consultarSetup()
      .then((d) => !cancelado && setPrecisaConfigurar(d.needs_setup))
      .catch(() => !cancelado && setPrecisaConfigurar(false));
    return () => {
      cancelado = true;
    };
  }, []);

  const alterar = (campo) => (evento) =>
    setForm((atual) => ({ ...atual, [campo]: evento.target.value }));

  const senhasDiferem =
    form.confirmacao.length > 0 && form.admin_password !== form.confirmacao;

  async function aoEnviar(evento) {
    evento.preventDefault();
    setErro("");

    if (form.admin_password !== form.confirmacao) {
      setErro("As senhas nao conferem.");
      return;
    }

    setEnviando(true);
    try {
      const dados = {
        company_name: form.company_name,
        admin_name: form.admin_name,
        admin_email: form.admin_email,
        admin_password: form.admin_password,
      };
      adotarSessao(await executarSetup(dados));
      navegar("/admin", { replace: true });
    } catch (e) {
      setErro(mensagemDeErro(e, "Nao foi possivel concluir a configuracao."));
    } finally {
      setEnviando(false);
    }
  }

  if (precisaConfigurar === null) {
    return <div className="carregando-tela">Carregando...</div>;
  }
  if (precisaConfigurar === false) {
    return <Navigate to="/entrar" replace />;
  }

  return (
    <div className="entrada">
      <div className="entrada__caixa entrada__caixa--larga">
        <p className="entrada__marca">Log Rotas</p>
        <p className="entrada__subtitulo">
          Primeiro acesso. Vamos cadastrar a empresa e o seu administrador.
        </p>

        <form className="entrada__formulario" onSubmit={aoEnviar} noValidate>
          {erro && <Alert tom="erro">{erro}</Alert>}

          <p className="entrada__grupo-titulo">Empresa</p>
          <InputField
            label="Nome da empresa"
            value={form.company_name}
            onChange={alterar("company_name")}
            required
            obrigatorio
            autoFocus
          />

          <hr className="entrada__separador" />

          <p className="entrada__grupo-titulo">Administrador</p>
          <InputField
            label="Seu nome"
            value={form.admin_name}
            onChange={alterar("admin_name")}
            autoComplete="name"
            required
            obrigatorio
          />
          <InputField
            label="E-mail"
            type="email"
            value={form.admin_email}
            onChange={alterar("admin_email")}
            autoComplete="username"
            inputMode="email"
            required
            obrigatorio
          />
          <InputField
            label="Senha"
            type="password"
            value={form.admin_password}
            onChange={alterar("admin_password")}
            autoComplete="new-password"
            ajuda={`Minimo de ${SENHA_MINIMA} caracteres.`}
            required
            obrigatorio
          />
          <InputField
            label="Confirme a senha"
            type="password"
            value={form.confirmacao}
            onChange={alterar("confirmacao")}
            autoComplete="new-password"
            erro={senhasDiferem ? "As senhas nao conferem." : ""}
            required
            obrigatorio
          />

          <Button type="submit" carregando={enviando} larguraTotal tamanho="grande">
            Criar acesso e entrar
          </Button>
        </form>

        <p className="entrada__rodape">
          Esta tela aparece uma unica vez. Depois dela, novos acessos sao criados
          pelo administrador.
        </p>
      </div>
    </div>
  );
}
