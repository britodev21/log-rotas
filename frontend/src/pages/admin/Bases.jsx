import { useState } from "react";
import { MapPin, MoreHorizontal, Pencil, Power, Star } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { bases as api } from "../../api/cadastros";
import { CadastroPage, GeocodeBadge } from "../../components/domain";
import {
  Alert,
  Badge,
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

const VAZIO = { name: "", address: "", phone: "", notes: "" };

export function Bases() {
  useDocumentTitle("Bases");
  const toast = useToast();
  const estado = useCadastro(api, { rotulo: "as bases" });

  const [modal, setModal] = useState(null);
  const [form, setForm] = useState(VAZIO);
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  const editando = modal && modal !== "nova";
  // Endereço alterado descarta a coordenada no backend; avisar antes evita
  // que a pessoa descubra isso depois, olhando o mapa.
  const trocouEndereco =
    editando && modal.address && form.address !== (modal.address ?? "");

  function abrir(base) {
    setErro("");
    if (base) {
      setForm({
        name: base.name ?? "",
        address: base.address ?? "",
        phone: base.phone ?? "",
        notes: base.notes ?? "",
      });
      setModal(base);
    } else {
      setForm(VAZIO);
      setModal("nova");
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
      address: form.address || null,
      phone: form.phone || null,
      notes: form.notes || null,
    };

    try {
      if (editando) {
        await api.alterar(modal.id, dados);
        toast.sucesso("Base atualizada");
      } else {
        const criada = await api.criar(dados);
        toast.sucesso(
          "Base cadastrada",
          criada.is_default
            ? `${criada.name} é a base padrão da operação.`
            : `${criada.name} está disponível para o planejamento.`,
        );
      }
      setModal(null);
      await estado.carregar();
    } catch (e) {
      console.error("Falha ao salvar base", e);
      setErro(mensagemDeErro(e, "Não foi possível salvar a base."));
    } finally {
      setSalvando(false);
    }
  }

  async function acao(base, dados, mensagem) {
    try {
      await api.alterar(base.id, dados);
      toast.sucesso(mensagem);
      await estado.carregar();
    } catch (e) {
      console.error("Falha ao alterar base", e);
      toast.erro("Não foi possível alterar", mensagemDeErro(e));
    }
  }

  return (
    <>
      <CadastroPage
        titulo="Bases"
        descricao="De onde os veículos saem e para onde voltam. A base padrão vem pré-selecionada no planejamento."
        icone={MapPin}
        rotuloSingular="base"
        rotuloPlural="bases"
        textoVazio="Cadastre a loja, o depósito ou a fábrica de onde as entregas saem."
        aoCriar={() => abrir(null)}
        estado={estado}
        colunas={4}
      >
        <Table>
          <THead>
            <TH>Base</TH>
            <TH largura="180px">Endereço</TH>
            <TH largura="150px">Localização</TH>
            <TH largura="120px">Situação</TH>
            <TH largura="60px">
              <span className="sr-apenas">Ações</span>
            </TH>
          </THead>
          <TBody>
            {estado.itens.map((b) => (
              <TR key={b.id}>
                <TD>
                  <div className="identificacao">
                    <span className="identificacao__icone" aria-hidden="true">
                      <MapPin size={16} strokeWidth={2} />
                    </span>
                    <div className="identificacao__texto">
                      <span className="identificacao__nome">
                        {b.name}
                        {b.is_default && <Badge tom="marca">padrão</Badge>}
                      </span>
                      {b.phone && (
                        <span className="identificacao__detalhe">{b.phone}</span>
                      )}
                    </div>
                  </div>
                </TD>

                <TD>
                  {b.address ? (
                    <span className="identificacao__detalhe">{b.address}</span>
                  ) : (
                    <span className="sem-dado">—</span>
                  )}
                </TD>

                <TD>
                  <GeocodeBadge status={b.geocode_status} semEndereco={!b.address} />
                </TD>

                <TD>
                  <StatusBadge tipo="usuario" valor={b.active ? "ATIVO" : "INATIVO"} />
                </TD>

                <TDAcoes>
                  <Dropdown
                    gatilho={
                      <Button
                        variante="sutil"
                        tamanho="sm"
                        icone={MoreHorizontal}
                        aria-label={`Ações de ${b.name}`}
                      />
                    }
                  >
                    <DropdownItem icone={Pencil} onClick={() => abrir(b)}>
                      Editar
                    </DropdownItem>
                    <DropdownItem
                      icone={Star}
                      onClick={() => acao(b, { is_default: true }, "Base padrão alterada")}
                      disabled={b.is_default || !b.active}
                    >
                      Definir como padrão
                    </DropdownItem>
                    <DropdownItem
                      icone={Power}
                      onClick={() =>
                        acao(
                          b,
                          { active: !b.active },
                          b.active ? "Base desativada" : "Base reativada",
                        )
                      }
                      perigo={b.active}
                    >
                      {b.active ? "Desativar" : "Reativar"}
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
        titulo={editando ? "Editar base" : "Nova base"}
        descricao={editando ? modal.name : "Ponto de partida e retorno das rotas."}
        onFechar={() => setModal(null)}
      >
        <form className="form-modal" onSubmit={enviar} noValidate>
          {erro && <Alert tom="erro">{erro}</Alert>}

          <InputField
            label="Nome"
            placeholder="Loja Centro"
            value={form.name}
            onChange={alterar("name")}
            required
            obrigatorio
          />

          <InputField
            label="Endereço"
            placeholder="Rua, número, bairro, cidade"
            value={form.address}
            onChange={alterar("address")}
            ajuda="Será convertido em coordenada quando a geocodificação entrar (Fase 4)."
          />

          {trocouEndereco && (
            <Alert tom="atencao" titulo="A localização será recalculada">
              Como o endereço mudou, a coordenada atual é descartada — ela
              apontaria para o lugar anterior.
            </Alert>
          )}

          <InputField
            label="Telefone"
            value={form.phone}
            onChange={alterar("phone")}
          />

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
              {editando ? "Salvar alterações" : "Cadastrar base"}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
