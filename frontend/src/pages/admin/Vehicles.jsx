import { useState } from "react";
import { MoreHorizontal, Pencil, Power, Truck } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { veiculos as api } from "../../api/cadastros";
import { CadastroPage } from "../../components/domain";
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

const VAZIO = {
  name: "",
  plate: "",
  model: "",
  capacity_weight_kg: "",
  capacity_volume_m3: "",
  capacity_length_m: "",
  max_stops: "",
  crew_size: "1",
  notes: "",
};

/** Campo numérico vazio vira null, não zero — zero seria um limite real. */
function numeroOuNulo(valor) {
  if (valor === "" || valor === null || valor === undefined) return null;
  const n = Number(valor);
  return Number.isFinite(n) ? n : null;
}

function Capacidades({ veiculo }) {
  const itens = [
    { valor: veiculo.capacity_weight_kg, unidade: "kg" },
    { valor: veiculo.capacity_volume_m3, unidade: "m³" },
    { valor: veiculo.capacity_length_m, unidade: "m" },
    { valor: veiculo.max_stops, unidade: "paradas" },
  ].filter((i) => i.valor !== null && i.valor !== undefined);

  // Capacidade não informada não vira zero na tela: zero significaria que o
  // veículo não carrega nada, e o que existe é ausência de informação.
  if (itens.length === 0) {
    return <span className="sem-dado">Não informada</span>;
  }

  return (
    <div className="capacidades">
      {itens.map((i) => (
        <span className="capacidade" key={i.unidade}>
          {Number(i.valor).toLocaleString("pt-BR")}
          <span className="capacidade__unidade">{i.unidade}</span>
        </span>
      ))}
    </div>
  );
}

export function Vehicles() {
  useDocumentTitle("Veículos");
  const toast = useToast();
  const estado = useCadastro(api, { rotulo: "os veículos" });

  const [modal, setModal] = useState(null); // null | "novo" | veiculo
  const [form, setForm] = useState(VAZIO);
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  const editando = modal && modal !== "novo";

  function abrir(veiculo) {
    setErro("");
    if (veiculo) {
      setForm({
        ...VAZIO,
        ...Object.fromEntries(
          Object.keys(VAZIO).map((k) => [k, veiculo[k] ?? ""]),
        ),
      });
      setModal(veiculo);
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
      plate: form.plate,
      model: form.model || null,
      capacity_weight_kg: numeroOuNulo(form.capacity_weight_kg),
      capacity_volume_m3: numeroOuNulo(form.capacity_volume_m3),
      capacity_length_m: numeroOuNulo(form.capacity_length_m),
      max_stops: numeroOuNulo(form.max_stops),
      crew_size: numeroOuNulo(form.crew_size) ?? 1,
      notes: form.notes || null,
    };

    try {
      if (editando) {
        await api.alterar(modal.id, dados);
        toast.sucesso("Veículo atualizado");
      } else {
        await api.criar(dados);
        toast.sucesso("Veículo cadastrado", `${dados.name} entrou na frota.`);
      }
      setModal(null);
      await estado.carregar();
    } catch (e) {
      console.error("Falha ao salvar veículo", e);
      setErro(mensagemDeErro(e, "Não foi possível salvar o veículo."));
    } finally {
      setSalvando(false);
    }
  }

  async function alternarSituacao(veiculo) {
    try {
      await api.alterar(veiculo.id, { active: !veiculo.active });
      toast.sucesso(veiculo.active ? "Veículo desativado" : "Veículo reativado");
      await estado.carregar();
    } catch (e) {
      console.error("Falha ao alterar veículo", e);
      toast.erro("Não foi possível alterar", mensagemDeErro(e));
    }
  }

  return (
    <>
      <CadastroPage
        titulo="Veículos"
        descricao="A frota disponível para as rotas. As capacidades são opcionais — informe as que realmente limitam a carga."
        icone={Truck}
        rotuloSingular="veículo"
        rotuloPlural="veículos"
        textoVazio="Cadastre a frota para que o planejador saiba com o que contar."
        aoCriar={() => abrir(null)}
        estado={estado}
        colunas={5}
      >
        <Table>
          <THead>
            <TH>Veículo</TH>
            <TH largura="130px">Placa</TH>
            <TH>Capacidade</TH>
            <TH largura="110px" numerico>
              Equipe
            </TH>
            <TH largura="120px">Situação</TH>
            <TH largura="60px">
              <span className="sr-apenas">Ações</span>
            </TH>
          </THead>
          <TBody>
            {estado.itens.map((v) => (
              <TR key={v.id}>
                <TD>
                  <div className="identificacao">
                    <span className="identificacao__icone" aria-hidden="true">
                      <Truck size={16} strokeWidth={2} />
                    </span>
                    <div className="identificacao__texto">
                      <span className="identificacao__nome">{v.name}</span>
                      {v.model && (
                        <span className="identificacao__detalhe">{v.model}</span>
                      )}
                    </div>
                  </div>
                </TD>

                <TD>
                  <span className="placa">{v.plate}</span>
                </TD>

                <TD>
                  <Capacidades veiculo={v} />
                </TD>

                <TD numerico>
                  <Badge tom={v.crew_size > 1 ? "info" : "neutro"}>
                    {v.crew_size} {v.crew_size === 1 ? "pessoa" : "pessoas"}
                  </Badge>
                </TD>

                <TD>
                  <StatusBadge tipo="usuario" valor={v.active ? "ATIVO" : "INATIVO"} />
                </TD>

                <TDAcoes>
                  <Dropdown
                    gatilho={
                      <Button
                        variante="sutil"
                        tamanho="sm"
                        icone={MoreHorizontal}
                        aria-label={`Ações de ${v.name}`}
                      />
                    }
                  >
                    <DropdownItem icone={Pencil} onClick={() => abrir(v)}>
                      Editar
                    </DropdownItem>
                    <DropdownItem
                      icone={Power}
                      onClick={() => alternarSituacao(v)}
                      perigo={v.active}
                    >
                      {v.active ? "Desativar" : "Reativar"}
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
        titulo={editando ? "Editar veículo" : "Novo veículo"}
        descricao={editando ? modal.name : "Adicione um veículo à frota."}
        onFechar={() => setModal(null)}
        tamanho="lg"
      >
        <form className="form-modal" onSubmit={enviar} noValidate>
          {erro && <Alert tom="erro">{erro}</Alert>}

          <div className="form-grade">
            <InputField
              label="Nome ou identificação"
              placeholder="Caminhão 1"
              value={form.name}
              onChange={alterar("name")}
              required
              obrigatorio
            />
            <InputField
              label="Placa"
              placeholder="ABC1D23"
              value={form.plate}
              onChange={alterar("plate")}
              ajuda="Formato antigo ou Mercosul."
              required
              obrigatorio
            />
          </div>

          <InputField
            label="Modelo"
            placeholder="Mercedes-Benz Accelo"
            value={form.model}
            onChange={alterar("model")}
          />

          <Alert tom="info" titulo="Preencha só o que limita a sua carga">
            Móveis costumam esgotar o espaço antes do peso, e uma peça de
            corrimão pode não caber por comprimento mesmo sendo leve. Cada
            campo preenchido vira uma restrição no cálculo das rotas; os vazios
            são ignorados.
          </Alert>

          <div className="form-grade">
            <InputField
              label="Peso máximo (kg)"
              type="number"
              min="0"
              step="0.01"
              value={form.capacity_weight_kg}
              onChange={alterar("capacity_weight_kg")}
            />
            <InputField
              label="Volume máximo (m³)"
              type="number"
              min="0"
              step="0.001"
              value={form.capacity_volume_m3}
              onChange={alterar("capacity_volume_m3")}
            />
            <InputField
              label="Comprimento máximo (m)"
              type="number"
              min="0"
              step="0.01"
              value={form.capacity_length_m}
              onChange={alterar("capacity_length_m")}
              ajuda="Maior peça que cabe no veículo."
            />
            <InputField
              label="Máximo de paradas"
              type="number"
              min="1"
              value={form.max_stops}
              onChange={alterar("max_stops")}
            />
          </div>

          <InputField
            label="Tamanho da equipe"
            type="number"
            min="1"
            max="20"
            value={form.crew_size}
            onChange={alterar("crew_size")}
            ajuda="Quantas pessoas saem neste veículo, incluindo o motorista."
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
              {editando ? "Salvar alterações" : "Cadastrar veículo"}
            </Button>
          </div>
        </form>
      </Modal>
    </>
  );
}
