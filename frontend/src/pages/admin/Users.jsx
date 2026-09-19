import { useCallback, useEffect, useState } from "react";

import { mensagemDeErro } from "../../api/client";
import {
  alterarUsuario,
  criarUsuario,
  listarUsuarios,
  redefinirSenha,
} from "../../api/users";
import {
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  InputField,
  Modal,
  PageHeader,
  SelectField,
} from "../../components/ui";
import { useAuth } from "../../hooks/useAuth";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import "./admin.css";

const PAPEIS = {
  ADMIN: "Administrador",
  MOTORISTA: "Motorista",
};

const FORM_VAZIO = { name: "", email: "", password: "", role: "MOTORISTA" };

export function Users() {
  useDocumentTitle("Usuarios");
  const { usuario: usuarioAtual } = useAuth();

  const [usuarios, setUsuarios] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [aviso, setAviso] = useState("");
  const [filtroPapel, setFiltroPapel] = useState("");
  const [busca, setBusca] = useState("");

  const [modalCriar, setModalCriar] = useState(false);
  const [form, setForm] = useState(FORM_VAZIO);
  const [erroForm, setErroForm] = useState("");
  const [salvando, setSalvando] = useState(false);

  const [modalSenha, setModalSenha] = useState(null);
  const [novaSenha, setNovaSenha] = useState("");

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro("");
    try {
      const filtros = {};
      if (filtroPapel) filtros.role = filtroPapel;
      if (busca.trim()) filtros.search = busca.trim();
      setUsuarios(await listarUsuarios(filtros));
    } catch (e) {
      setErro(mensagemDeErro(e, "Nao foi possivel carregar os usuarios."));
    } finally {
      setCarregando(false);
    }
  }, [filtroPapel, busca]);

  // Debounce na busca: evita uma chamada por tecla digitada.
  useEffect(() => {
    const id = setTimeout(carregar, busca ? 300 : 0);
    return () => clearTimeout(id);
  }, [carregar, busca]);

  const alterarForm = (campo) => (e) =>
    setForm((atual) => ({ ...atual, [campo]: e.target.value }));

  function abrirCriacao() {
    setForm(FORM_VAZIO);
    setErroForm("");
    setModalCriar(true);
  }

  function abrirRedefinicao(alvo) {
    setErroForm("");
    setNovaSenha("");
    setModalSenha(alvo);
  }

  async function salvarNovo(evento) {
    evento.preventDefault();
    setErroForm("");
    setSalvando(true);
    try {
      await criarUsuario(form);
      setModalCriar(false);
      setAviso(`Acesso de ${form.name} criado.`);
      setForm(FORM_VAZIO);
      await carregar();
    } catch (e) {
      setErroForm(mensagemDeErro(e, "Nao foi possivel criar o usuario."));
    } finally {
      setSalvando(false);
    }
  }

  async function alternarSituacao(alvo) {
    setErro("");
    setAviso("");
    try {
      await alterarUsuario(alvo.id, { active: !alvo.active });
      await carregar();
    } catch (e) {
      setErro(mensagemDeErro(e, "Nao foi possivel alterar o usuario."));
    }
  }

  async function confirmarNovaSenha(evento) {
    evento.preventDefault();
    setErroForm("");
    setSalvando(true);
    try {
      await redefinirSenha(modalSenha.id, novaSenha);
      setAviso(
        `Senha de ${modalSenha.name} redefinida. Informe a nova senha pessoalmente.`,
      );
      setModalSenha(null);
      setNovaSenha("");
    } catch (e) {
      setErroForm(mensagemDeErro(e, "Nao foi possivel redefinir a senha."));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <>
      <PageHeader
        titulo="Usuarios"
        descricao="Quem entra no sistema. Cada motorista precisa de um acesso para receber a rota no celular."
        acoes={<Button onClick={abrirCriacao}>Novo usuario</Button>}
      />

      {erro && <Alert tom="erro">{erro}</Alert>}
      {aviso && <Alert tom="sucesso">{aviso}</Alert>}

      <Card>
        <div className="filtros">
          <InputField
            label="Buscar"
            placeholder="Nome ou e-mail"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
          />
          <SelectField
            label="Papel"
            value={filtroPapel}
            onChange={(e) => setFiltroPapel(e.target.value)}
          >
            <option value="">Todos</option>
            <option value="ADMIN">Administrador</option>
            <option value="MOTORISTA">Motorista</option>
          </SelectField>
        </div>

        {carregando && <p className="texto-suave">Carregando...</p>}

        {!carregando && usuarios.length === 0 && (
          <EmptyState titulo="Nenhum usuario encontrado">
            <p>Ajuste os filtros ou cadastre um novo acesso.</p>
          </EmptyState>
        )}

        {!carregando && usuarios.length > 0 && (
          <div className="tabela-area">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Usuario</th>
                  <th>Papel</th>
                  <th>Situacao</th>
                  <th>
                    <span className="sr-apenas">Acoes</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {usuarios.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <span className="tabela__principal">{u.name}</span>
                      <span className="tabela__secundario">{u.email}</span>
                    </td>
                    <td>
                      <Badge tom={u.role === "ADMIN" ? "info" : "neutro"}>
                        {PAPEIS[u.role] ?? u.role}
                      </Badge>
                    </td>
                    <td>
                      <Badge tom={u.active ? "sucesso" : "erro"}>
                        {u.active ? "Ativo" : "Inativo"}
                      </Badge>
                    </td>
                    <td>
                      <div className="tabela__acoes">
                        <Button variante="texto" onClick={() => abrirRedefinicao(u)}>
                          Redefinir senha
                        </Button>
                        <Button
                          variante="texto"
                          onClick={() => alternarSituacao(u)}
                          disabled={u.id === usuarioAtual?.id}
                          title={
                            u.id === usuarioAtual?.id
                              ? "Voce nao pode desativar o proprio acesso."
                              : undefined
                          }
                        >
                          {u.active ? "Desativar" : "Ativar"}
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal
        aberto={modalCriar}
        titulo="Novo usuario"
        onFechar={() => setModalCriar(false)}
      >
        <form className="formulario-modal" onSubmit={salvarNovo} noValidate>
          {erroForm && <Alert tom="erro">{erroForm}</Alert>}

          <InputField
            label="Nome"
            value={form.name}
            onChange={alterarForm("name")}
            required
            obrigatorio
            autoFocus
          />
          <InputField
            label="E-mail"
            type="email"
            value={form.email}
            onChange={alterarForm("email")}
            inputMode="email"
            required
            obrigatorio
          />
          <SelectField label="Papel" value={form.role} onChange={alterarForm("role")}>
            <option value="MOTORISTA">Motorista</option>
            <option value="ADMIN">Administrador</option>
          </SelectField>
          <InputField
            label="Senha provisoria"
            type="password"
            value={form.password}
            onChange={alterarForm("password")}
            ajuda="Minimo de 10 caracteres. Informe ao usuario pessoalmente."
            autoComplete="new-password"
            required
            obrigatorio
          />

          <div className="tabela__acoes">
            <Button variante="secundario" onClick={() => setModalCriar(false)}>
              Cancelar
            </Button>
            <Button type="submit" carregando={salvando}>
              Criar acesso
            </Button>
          </div>
        </form>
      </Modal>

      <Modal
        aberto={Boolean(modalSenha)}
        titulo={`Redefinir senha de ${modalSenha?.name ?? ""}`}
        onFechar={() => setModalSenha(null)}
      >
        <form className="formulario-modal" onSubmit={confirmarNovaSenha} noValidate>
          {erroForm && <Alert tom="erro">{erroForm}</Alert>}

          <Alert tom="atencao">
            As sessoes abertas deste usuario serao encerradas.
          </Alert>

          <InputField
            label="Nova senha"
            type="password"
            value={novaSenha}
            onChange={(e) => setNovaSenha(e.target.value)}
            ajuda="Minimo de 10 caracteres."
            autoComplete="new-password"
            required
            obrigatorio
            autoFocus
          />

          <div className="tabela__acoes">
            <Button variante="secundario" onClick={() => setModalSenha(null)}>
              Cancelar
            </Button>
            <Button type="submit" carregando={salvando}>
              Redefinir
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
