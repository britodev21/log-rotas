import { useEffect, useState } from "react";
import { MoreHorizontal, Pencil, Power, UserCog } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { motoristas as api } from "../../api/cadastros";
import { listarUsuarios } from "../../api/users";
import { CadastroPage } from "../../components/domain";
import {
  Alert,
  Avatar,
  Badge,
  Button,
  Dropdown,
  DropdownItem,
  InputField,
  Modal,
  SelectField,
  StatusBadge,
  TBody,
  TD,
  TDAcoes,
  TH,
  THead,
  TR,
  Table,
  TextareaField,
} from "../../components/ui";
import { useCadastro } from "../../hooks/useCadastro";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useToast } from "../../hooks/useToast";
import "./admin.css";

const VAZIO = {
  name: "",
  user_id: "",
  phone: "",
  document: "",
  license_number: "",
  license_expires_at: "",
  notes: "",
};

export function Drivers() {
  useDocumentTitle("Motoristas");
  const toast = useToast();
  const estado = useCadastro(api, { rotulo: "os motoristas" });

  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(VAZIO);
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [acessos, setAcessos] = useState([]);

  const editando = modal && modal !== "novo";

  // Só usuários com perfil de motorista podem ser vinculados — o backend
  // recusa os demais, e oferecer administradores na lista seria convidar ao
  // erro.
  useEffect(() => {
    if (!modal) return;
    listarUsuarios({ role: "MOTORISTA", active: true })
      .then(setAcessos)
      .catch((e) => console.error("Falha ao listar acessos de motorista", e));
  }, [modal]);

  function abrir(motorista) {
    setErro("");
    if (motorista) {
      setForm({
        name: motorista.name ?? "",
        user_id: motorista.user_id ? String(motorista.user_id) : "",
        phone: motorista.phone ?? "",
        document: motorista.document ?? "",
        license_number: motorista.license_number ?? "",
        license_expires_at: motorista.license_expires_at ?? "",
        notes: motorista.notes ?? "",
      });
      setModal(motorista);
    } else {
      setForm(VAZIO);
      setModal("novo");
    }
  }

  const alterar = (campo) => (e) =>
    setForm((atual) => ({ ...atual, [campo]: e.target.value }));

  async function enviar(evento) {
    evento.preventDefault();
    setErro("");
    setSalvando(true);

    const dados = {
      name: form.name,
      user_id: form.user_id ? Number(form.user_id) : null,
      phone: form.phone || null,
      document: form.document || null,
      license_number: form.license_number || null,
      license_expires_at: form.license_expires_at || null,
      notes: form.notes || null,
    };

    try {
      if (editando) {
        await api.alterar(modal.id, dados);
        toast.sucesso("Motorista atualizado");
      } else {
        await api.criar(dados);
        toast.sucesso("Motorista cadastrado", `${dados.name} já pode receber rotas.`);
      }
      setModal(null);
      await estado.carregar();
    } catch (e) {
      console.error("Falha ao salvar motorista", e);
      setErro(mensagemDeErro(e, "Não foi possível salvar o motorista."));
    } finally {
      setSalvando(false);
    }
  }

  async function alternarSituacao(motorista) {
    try {
      await api.alterar(motorista.id, { active: !motorista.active });
      toast.sucesso(motorista.active ? "Motorista desativado" : "Motorista reativado");
      await estado.carregar();
    } catch (e) {
      console.error("Falha ao alterar motorista", e);
      toast.erro("Não foi possível alterar", mensagemDeErro(e));
    }
  }

  return (
    <>
      <CadastroPage
        titulo="Motoristas"
        descricao="Quem executa as rotas. O acesso ao sistema é opcional — terceirizado aparece no planejamento do mesmo jeito."
        icone={UserCog}
        rotuloSingular="motorista"
        rotuloPlural="motoristas"
        textoVazio="Cadastre quem dirige para poder atribuir rotas a eles."
        aoCriar={() => abrir(null)}
        estado={estado}
        colunas={4}
      >
        <Table>
          <THead>
            <TH>Motorista</TH>
            <TH largura="200px">Acesso ao sistema</TH>
            <TH largura="150px">CNH</TH>
            <TH largura="120px">Situação</TH>
            <TH largura="60px">
              <span className="sr-apenas">Ações</span>
            </TH>
          </THead>
          <TBody>
            {estado.itens.map((m) => (
              <TR key={m.id}>
                <TD>
                  <div className="identificacao">
                    <Avatar nome={m.name} tamanho={32} />
                    <div className="identificacao__texto">
                      <span className="identificacao__nome">{m.name}</span>
                      {m.phone && (
                        <span className="identificacao__detalhe">{m.phone}</span>
                      )}
                    </div>
                  </div>
                </TD>

                <TD>
                  {m.user ? (
                    <span className="identificacao__detalhe">{m.user.email}</span>
                  ) : (
                    <Badge tom="neutro">Sem acesso</Badge>
                  )}
                </TD>

                <TD>
                  {m.license_number ? (
                    <span className="identificacao__detalhe">{m.license_number}</span>
                  ) : (
                    <span className="sem-dado">—</span>
                  )}
                </TD>

                <TD>
                  <StatusBadge tipo="usuario" valor={m.active ? "ATIVO" : "INATIVO"} />
                </TD>

                <TDAcoes>
                  <Dropdown
                    gatilho={
                      <Button
                        variante="sutil"
                        tamanho="sm"
                        icone={MoreHorizontal}
                        aria-label={`Ações de ${m.name}`}
                      />
                    }
                  >
                    <DropdownItem icone={Pencil} onClick={() => abrir(m)}>
                      Editar
                    </DropdownItem>
                    <DropdownItem
                      icone={Power}
                      onClick={() => alternarSituacao(m)}
                      perigo={m.active}
                    >
                      {m.active ? "Desativar" : "Reativar"}
                    </DropdownItem>
                  </Dropdown>
                </TDAcoes>
              </TR>
            ))}
          </TBody>
        </Table>
      </CadastroPage>

      <Modal
        aberto={Boolean(modal)}
        titulo={editando ? "Editar motorista" : "Novo motorista"}
        descricao={editando ? modal.name : "Quem vai executar as rotas."}
        onFechar={() => setModal(null)}
        tamanho="lg"
      >
        <form className="form-modal" onSubmit={enviar} noValidate>
          {erro && <Alert tom="erro">{erro}</Alert>}

          <InputField
            label="Nome"
            value={form.name}
            onChange={alterar("name")}
            required
            obrigatorio
          />

          <SelectField
            label="Acesso ao sistema"
            value={form.user_id}
            onChange={alterar("user_id")}
            ajuda="Necessário apenas para quem vai usar o aplicativo no celular."
          >
            <option value="">Sem acesso</option>
            {acessos.map((u) => (
              <option value={String(u.id)} key={u.id}>
                {u.name} — {u.email}
              </option>
            ))}
          </SelectField>

          {acessos.length === 0 && (
            <Alert tom="info">
              Nenhum acesso com perfil de motorista foi criado ainda. Você pode
              cadastrar o motorista agora e vincular o acesso depois, em
              Usuários.
            </Alert>
          )}

          <div className="form-grade">
            <InputField label="Telefone" value={form.phone} onChange={alterar("phone")} />
            <InputField label="CPF" value={form.document} onChange={alterar("document")} />
            <InputField
              label="Número da CNH"
              value={form.license_number}
              onChange={alterar("license_number")}
            />
            <InputField
              label="Validade da CNH"
              type="date"
              value={form.license_expires_at}
              onChange={alterar("license_expires_at")}
            />
          </div>

          <TextareaField
            label="Observações"
            value={form.notes}
            onChange={alterar("notes")}
          />

          <div className="acoes-direita">
            <Button variante="secundario" onClick={() => setModal(null)}>
              Cancelar
            </Button>
            <Button type="submit" carregando={salvando}>
              {editando ? "Salvar alterações" : "Cadastrar motorista"}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
