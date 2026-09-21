import { useState } from "react";
import { MoreHorizontal, Pencil, Power, Users } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { clientes as api } from "../../api/cadastros";
import { CadastroPage, CampoEndereco, GeocodeBadge } from "../../components/domain";
import {
  Alert,
  Avatar,
  Button,
  Dropdown,
  DropdownItem,
  InputField,
  Modal,
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
  phone: "",
  email: "",
  document: "",
  notes: "",
};

export function Customers() {
  useDocumentTitle("Clientes");
  const toast = useToast();
  const estado = useCadastro(api, { rotulo: "os clientes" });

  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(VAZIO);
  const [endereco, setEndereco] = useState({});
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  const editando = modal && modal !== "novo";

  function abrir(cliente) {
    setErro("");
    if (cliente) {
      setForm(
        Object.fromEntries(Object.keys(VAZIO).map((k) => [k, cliente[k] ?? ""])),
      );
      setEndereco({
        address: cliente.address ?? "",
        postal_code: cliente.postal_code ?? "",
        latitude: cliente.latitude,
        longitude: cliente.longitude,
      });
      setModal(cliente);
    } else {
      setForm(VAZIO);
      setEndereco({});
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
      phone: form.phone || null,
      email: form.email || null,
      document: form.document || null,
      address: endereco.address || null,
      postal_code: endereco.postal_code || null,
      latitude: endereco.latitude ?? null,
      longitude: endereco.longitude ?? null,
      notes: form.notes || null,
    };

    try {
      if (editando) {
        await api.alterar(modal.id, dados);
        toast.sucesso("Cliente atualizado");
      } else {
        await api.criar(dados);
        toast.sucesso("Cliente cadastrado", dados.name);
      }
      setModal(null);
      await estado.carregar();
    } catch (e) {
      console.error("Falha ao salvar cliente", e);
      setErro(mensagemDeErro(e, "Não foi possível salvar o cliente."));
    } finally {
      setSalvando(false);
    }
  }

  async function alternarSituacao(cliente) {
    try {
      await api.alterar(cliente.id, { active: !cliente.active });
      toast.sucesso(cliente.active ? "Cliente desativado" : "Cliente reativado");
      await estado.carregar();
    } catch (e) {
      console.error("Falha ao alterar cliente", e);
      toast.erro("Não foi possível alterar", mensagemDeErro(e));
    }
  }

  return (
    <>
      <CadastroPage
        titulo="Clientes"
        descricao="Quem compra com frequência. Para venda avulsa não é preciso cadastrar — a entrega carrega o próprio endereço."
        icone={Users}
        rotuloSingular="cliente"
        rotuloPlural="clientes"
        textoVazio="Cadastre construtoras, marcenarias e revendas para não redigitar o endereço a cada pedido."
        aoCriar={() => abrir(null)}
        estado={estado}
        colunas={4}
      >
        <Table>
          <THead>
            <TH>Cliente</TH>
            <TH largura="200px">Endereço</TH>
            <TH largura="150px">Localização</TH>
            <TH largura="120px">Situação</TH>
            <TH largura="60px">
              <span className="sr-apenas">Ações</span>
            </TH>
          </THead>
          <TBody>
            {estado.itens.map((c) => (
              <TR key={c.id}>
                <TD>
                  <div className="identificacao">
                    <Avatar nome={c.name} tamanho={32} />
                    <div className="identificacao__texto">
                      <span className="identificacao__nome">{c.name}</span>
                      {c.phone && (
                        <span className="identificacao__detalhe">{c.phone}</span>
                      )}
                    </div>
                  </div>
                </TD>

                <TD>
                  {c.address ? (
                    <span className="identificacao__detalhe">{c.address}</span>
                  ) : (
                    <span className="sem-dado">—</span>
                  )}
                </TD>

                <TD>
                  <GeocodeBadge status={c.geocode_status} semEndereco={!c.address} />
                </TD>

                <TD>
                  <StatusBadge tipo="usuario" valor={c.active ? "ATIVO" : "INATIVO"} />
                </TD>

                <TDAcoes>
                  <Dropdown
                    gatilho={
                      <Button
                        variante="sutil"
                        tamanho="sm"
                        icone={MoreHorizontal}
                        aria-label={`Ações de ${c.name}`}
                      />
                    }
                  >
                    <DropdownItem icone={Pencil} onClick={() => abrir(c)}>
                      Editar
                    </DropdownItem>
                    <DropdownItem
                      icone={Power}
                      onClick={() => alternarSituacao(c)}
                      perigo={c.active}
                    >
                      {c.active ? "Desativar" : "Reativar"}
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
        titulo={editando ? "Editar cliente" : "Novo cliente"}
        descricao={editando ? modal.name : "Cadastro de quem recebe entregas."}
        onFechar={() => setModal(null)}
        tamanho="lg"
      >
        <form className="form-modal" onSubmit={enviar} noValidate>
          {erro && <Alert tom="erro">{erro}</Alert>}

          <InputField
            label="Nome ou razão social"
            value={form.name}
            onChange={alterar("name")}
            required
            obrigatorio
          />
          <span className="rotulo-secao">Endereço</span>
          <CampoEndereco
            key={editando ? modal.id : "novo"}
            valor={endereco}
            aoMudar={setEndereco}
          />


          <div className="form-grade">
            <InputField label="Telefone" value={form.phone} onChange={alterar("phone")} />
            <InputField
              label="CPF ou CNPJ"
              value={form.document}
              onChange={alterar("document")}
              ajuda="Impede cadastrar o mesmo cliente duas vezes."
            />
          </div>

          <InputField
            label="E-mail"
            type="email"
            value={form.email}
            onChange={alterar("email")}
          />

          <TextareaField
            label="Observações"
            placeholder="Ponto de referência, horário de recebimento, cuidados no acesso"
            value={form.notes}
            onChange={alterar("notes")}
          />

          <div className="acoes-direita">
            <Button variante="secundario" onClick={() => setModal(null)}>
              Cancelar
            </Button>
            <Button type="submit" carregando={salvando}>
              {editando ? "Salvar alterações" : "Cadastrar cliente"}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
