import { useCallback, useEffect, useState } from "react";
import { KeyRound, MoreHorizontal, Plus, Search, UserX, Users as UsersIcon } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { alterarUsuario, listarUsuarios } from "../../api/users";
import {
  Avatar,
  Badge,
  Button,
  Card,
  Dropdown,
  DropdownItem,
  EmptyState,
  ErrorState,
  InputField,
  PageHeader,
  SelectField,
  SkeletonTable,
  StatusBadge,
  TBody,
  TD,
  TDAcoes,
  TH,
  THead,
  TR,
  Table,
} from "../../components/ui";
import { useAuth } from "../../hooks/useAuth";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useToast } from "../../hooks/useToast";
import { ModalNovoUsuario, ModalRedefinirSenha } from "./UserModals";
import "./admin.css";

const PAPEL = { ADMIN: "Administrador", MOTORISTA: "Motorista" };

export function Users() {
  useDocumentTitle("Usuários");
  const { usuario: usuarioAtual } = useAuth();
  const toast = useToast();

  const [usuarios, setUsuarios] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [filtroPapel, setFiltroPapel] = useState("");
  const [busca, setBusca] = useState("");

  const [modalNovo, setModalNovo] = useState(false);
  const [alvoSenha, setAlvoSenha] = useState(null);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro("");
    try {
      const filtros = {};
      if (filtroPapel) filtros.role = filtroPapel;
      if (busca.trim()) filtros.search = busca.trim();
      setUsuarios(await listarUsuarios(filtros));
    } catch (e) {
      // Detalhe técnico vai para o console; a tela mostra frase em português.
      console.error("Falha ao listar usuários", e);
      setErro(mensagemDeErro(e, "Não foi possível carregar os usuários."));
    } finally {
      setCarregando(false);
    }
  }, [filtroPapel, busca]);

  // Espera a digitação parar antes de consultar: sem isso seria uma
  // requisição por tecla pressionada.
  useEffect(() => {
    const id = setTimeout(carregar, busca ? 300 : 0);
    return () => clearTimeout(id);
  }, [carregar, busca]);

  async function alternarSituacao(alvo) {
    try {
      await alterarUsuario(alvo.id, { active: !alvo.active });
      toast.sucesso(
        alvo.active ? "Acesso desativado" : "Acesso reativado",
        alvo.active
          ? `${alvo.name} foi desconectado do sistema.`
          : `${alvo.name} pode entrar novamente.`,
      );
      await carregar();
    } catch (e) {
      console.error("Falha ao alterar usuário", e);
      toast.erro("Não foi possível alterar", mensagemDeErro(e));
    }
  }

  const semFiltro = !busca.trim() && !filtroPapel;

  return (
    <>
      <PageHeader
        titulo="Usuários"
        descricao="Quem tem acesso ao Log Rotas. Cada motorista precisa de um login próprio para receber a rota no celular."
        acoes={
          <Button icone={Plus} onClick={() => setModalNovo(true)}>
            Novo usuário
          </Button>
        }
      />

      <Card semPadding>
        <div className="filtros">
          <div className="filtros__busca">
            <InputField
              label="Buscar"
              placeholder="Nome ou e-mail"
              icone={Search}
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
          </div>

          <div className="filtros__campo">
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

          {!carregando && !erro && usuarios.length > 0 && (
            <span className="filtros__contagem numero">
              {usuarios.length} {usuarios.length === 1 ? "usuário" : "usuários"}
            </span>
          )}
        </div>

        {carregando && <SkeletonTable linhas={4} colunas={4} />}

        {!carregando && erro && (
          <ErrorState
            titulo="Não foi possível carregar os usuários"
            mensagem={erro}
            aoTentarNovamente={carregar}
          />
        )}

        {!carregando && !erro && usuarios.length === 0 && (
          <EmptyState
            icone={UsersIcon}
            titulo={semFiltro ? "Nenhum usuário por aqui" : "Nada encontrado"}
            acao={
              semFiltro ? (
                <Button icone={Plus} onClick={() => setModalNovo(true)}>
                  Cadastrar usuário
                </Button>
              ) : (
                <Button
                  variante="secundario"
                  onClick={() => {
                    setBusca("");
                    setFiltroPapel("");
                  }}
                >
                  Limpar filtros
                </Button>
              )
            }
          >
            <p>
              {semFiltro
                ? "Crie o acesso da equipe para que cada pessoa entre com o próprio login."
                : "Nenhum usuário corresponde à busca ou ao filtro selecionado."}
            </p>
          </EmptyState>
        )}

        {!carregando && !erro && usuarios.length > 0 && (
          <Table>
            <THead>
              <TH>Usuário</TH>
              <TH largura="180px">Papel</TH>
              <TH largura="140px">Situação</TH>
              <TH largura="60px">
                <span className="sr-apenas">Ações</span>
              </TH>
            </THead>
            <TBody>
              {usuarios.map((u) => (
                <TR key={u.id}>
                  <TD>
                    <div className="usuario-celula">
                      <Avatar nome={u.name} tamanho={32} />
                      <div className="usuario-celula__texto">
                        <span className="usuario-celula__nome">
                          {u.name}
                          {u.id === usuarioAtual?.id && (
                            <Badge tom="marca">você</Badge>
                          )}
                        </span>
                        <span className="usuario-celula__email">{u.email}</span>
                      </div>
                    </div>
                  </TD>

                  <TD>{PAPEL[u.role] ?? u.role}</TD>

                  <TD>
                    <StatusBadge tipo="usuario" valor={u.active ? "ATIVO" : "INATIVO"} />
                  </TD>

                  <TDAcoes>
                    <Dropdown
                      gatilho={
                        <Button
                          variante="sutil"
                          tamanho="sm"
                          icone={MoreHorizontal}
                          aria-label={`Ações de ${u.name}`}
                        />
                      }
                    >
                      <DropdownItem icone={KeyRound} onClick={() => setAlvoSenha(u)}>
                        Redefinir senha
                      </DropdownItem>
                      <DropdownItem
                        icone={UserX}
                        onClick={() => alternarSituacao(u)}
                        disabled={u.id === usuarioAtual?.id}
                        perigo={u.active}
                      >
                        {u.active ? "Desativar acesso" : "Reativar acesso"}
                      </DropdownItem>
                    </Dropdown>
                  </TDAcoes>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </Card>

      <ModalNovoUsuario
        aberto={modalNovo}
        onFechar={() => setModalNovo(false)}
        onCriado={carregar}
      />

      <ModalRedefinirSenha usuario={alvoSenha} onFechar={() => setAlvoSenha(null)} />
    </>
  );
}
