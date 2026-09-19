import { useState } from "react";

import { mensagemDeErro } from "../../api/client";
import { criarUsuario, redefinirSenha } from "../../api/users";
import { Alert, Button, InputField, Modal, SelectField } from "../../components/ui";
import { useToast } from "../../hooks/useToast";
import "./admin.css";

const FORM_VAZIO = { name: "", email: "", password: "", role: "MOTORISTA" };

/**
 * Modais de usuário, separados da listagem.
 *
 * A tela de usuários juntava lista, filtros e dois formulários num arquivo
 * só. Separar aqui mantém cada parte legível e é o padrão que as telas de
 * cadastro da Fase 3 vão seguir.
 */

export function ModalNovoUsuario({ aberto, onFechar, onCriado }) {
  const toast = useToast();
  const [form, setForm] = useState(FORM_VAZIO);
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  const alterar = (campo) => (e) =>
    setForm((atual) => ({ ...atual, [campo]: e.target.value }));

  function fechar() {
    setForm(FORM_VAZIO);
    setErro("");
    onFechar();
  }

  async function enviar(evento) {
    evento.preventDefault();
    setErro("");
    setSalvando(true);
    try {
      await criarUsuario(form);
      toast.sucesso(
        "Acesso criado",
        `${form.name} já pode entrar no sistema com o e-mail informado.`,
      );
      fechar();
      onCriado();
    } catch (e) {
      console.error("Falha ao criar usuário", e);
      setErro(mensagemDeErro(e, "Não foi possível criar o usuário."));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal
      aberto={aberto}
      titulo="Novo usuário"
      descricao="Crie o acesso de quem vai usar o Log Rotas."
      onFechar={fechar}
    >
      <form className="form-modal" onSubmit={enviar} noValidate>
        {erro && <Alert tom="erro">{erro}</Alert>}

        <InputField
          label="Nome"
          value={form.name}
          onChange={alterar("name")}
          autoComplete="off"
          required
          obrigatorio
        />

        <InputField
          label="E-mail"
          type="email"
          value={form.email}
          onChange={alterar("email")}
          inputMode="email"
          autoComplete="off"
          required
          obrigatorio
        />

        <SelectField
          label="Papel"
          value={form.role}
          onChange={alterar("role")}
          ajuda={
            form.role === "ADMIN"
              ? "Administradores podem cadastrar, planejar e alterar configurações."
              : "Motoristas veem apenas a própria rota e as próprias entregas."
          }
        >
          <option value="MOTORISTA">Motorista</option>
          <option value="ADMIN">Administrador</option>
        </SelectField>

        <InputField
          label="Senha provisória"
          type="password"
          value={form.password}
          onChange={alterar("password")}
          ajuda="Mínimo de 10 caracteres. Informe ao usuário pessoalmente."
          autoComplete="new-password"
          required
          obrigatorio
        />

        <div className="acoes-direita">
          <Button variante="secundario" onClick={fechar}>
            Cancelar
          </Button>
          <Button type="submit" carregando={salvando}>
            Criar acesso
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function ModalRedefinirSenha({ usuario, onFechar }) {
  const toast = useToast();
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  function fechar() {
    setSenha("");
    setErro("");
    onFechar();
  }

  async function enviar(evento) {
    evento.preventDefault();
    setErro("");
    setSalvando(true);
    try {
      await redefinirSenha(usuario.id, senha);
      toast.sucesso(
        "Senha redefinida",
        `Informe a nova senha a ${usuario.name} pessoalmente.`,
      );
      fechar();
    } catch (e) {
      console.error("Falha ao redefinir senha", e);
      setErro(mensagemDeErro(e, "Não foi possível redefinir a senha."));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal
      aberto={Boolean(usuario)}
      titulo="Redefinir senha"
      descricao={usuario?.name}
      onFechar={fechar}
      tamanho="sm"
    >
      <form className="form-modal" onSubmit={enviar} noValidate>
        {erro && <Alert tom="erro">{erro}</Alert>}

        <Alert tom="atencao">
          As sessões abertas deste usuário serão encerradas na hora.
        </Alert>

        <InputField
          label="Nova senha"
          type="password"
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          ajuda="Mínimo de 10 caracteres."
          autoComplete="new-password"
          required
          obrigatorio
        />

        <div className="acoes-direita">
          <Button variante="secundario" onClick={fechar}>
            Cancelar
          </Button>
          <Button type="submit" carregando={salvando}>
            Redefinir
          </Button>
        </div>
      </form>
    </Modal>
  );
}
