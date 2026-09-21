import { useEffect, useState } from "react";

import { mensagemDeErro } from "../../api/client";
import { entregas as api } from "../../api/operacao";
import { CampoEndereco } from "../../components/domain";
import {
  Alert,
  Button,
  InputField,
  Modal,
  SelectField,
  SkeletonText,
  StatusBadge,
  TextareaField,
} from "../../components/ui";
import { useToast } from "../../hooks/useToast";
import { MOTIVOS_INSUCESSO, PRIORIDADES, dataHora } from "../../utils/formato";
import "./admin.css";

const VAZIO = {
  customer_id: "",
  recipient_name: "",
  recipient_phone: "",
  description: "",
  order_number: "",
  weight_kg: "",
  volume_m3: "",
  length_m: "",
  required_crew: "1",
  service_time_minutes: "",
  priority: "NORMAL",
  time_window_start: "",
  time_window_end: "",
  notes: "",
};

function numeroOuNulo(valor) {
  if (valor === "" || valor === null || valor === undefined) return null;
  const n = Number(valor);
  return Number.isFinite(n) ? n : null;
}

export function ModalEntrega({ alvo, clientes, dataPadrao, onFechar, onSalvo }) {
  const toast = useToast();
  const editando = alvo && alvo !== "nova";

  const [form, setForm] = useState({ ...VAZIO, scheduled_date: dataPadrao });
  const [endereco, setEndereco] = useState({});
  const [erro, setErro] = useState("");
  const [salvando, setSalvando] = useState(false);

  useEffect(() => {
    if (!alvo) return;
    setErro("");
    if (editando) {
      setForm({
        ...VAZIO,
        ...Object.fromEntries(
          Object.keys(VAZIO).map((k) => [k, alvo[k] ?? ""]),
        ),
        scheduled_date: alvo.scheduled_date,
      });
    } else {
      setForm({ ...VAZIO, scheduled_date: dataPadrao });
    }
    setEndereco(
      editando
        ? {
            address: alvo.address ?? "",
            postal_code: alvo.postal_code ?? "",
            latitude: alvo.latitude,
            longitude: alvo.longitude,
            geocode_status: alvo.geocode_status,
            geocode_precision: alvo.geocode_precision,
          }
        : {},
    );
  }, [alvo, editando, dataPadrao]);

  const alterar = (campo) => (e) =>
    setForm((atual) => ({ ...atual, [campo]: e.target.value }));

  // Entrega já em rota trava os campos que afetam o planejamento — o
  // backend recusa, e avisar antes evita a pessoa preencher para nada.
  const travada = editando && ["EM_ROTA", "CHEGOU", "ENTREGUE"].includes(alvo.status);

  async function enviar(evento) {
    evento.preventDefault();
    setErro("");
    setSalvando(true);

    const dados = {
      customer_id: form.customer_id ? Number(form.customer_id) : null,
      recipient_name: form.recipient_name || null,
      recipient_phone: form.recipient_phone || null,
      address: endereco.address || null,
      postal_code: endereco.postal_code || null,
      latitude: endereco.latitude ?? null,
      longitude: endereco.longitude ?? null,
      // Só o que uma pessoa marcou no mapa vale como confirmado. Sem esta
      // linha o backend guardaria o palpite do geocodificador como MANUAL,
      // e a entrega entraria em rota apontando para a quadra errada.
      ponto_confirmado: Boolean(endereco.ponto_confirmado),
      google_place_id: endereco.google_place_id || null,
      description: form.description || null,
      order_number: form.order_number || null,
      weight_kg: numeroOuNulo(form.weight_kg),
      volume_m3: numeroOuNulo(form.volume_m3),
      length_m: numeroOuNulo(form.length_m),
      required_crew: numeroOuNulo(form.required_crew) ?? 1,
      service_time_minutes: numeroOuNulo(form.service_time_minutes),
      priority: form.priority,
      time_window_start: form.time_window_start || null,
      time_window_end: form.time_window_end || null,
      notes: form.notes || null,
      scheduled_date: form.scheduled_date,
    };

    try {
      if (editando) {
        await api.alterar(alvo.id, dados);
        toast.sucesso("Entrega atualizada");
      } else {
        await api.criar(dados);
        toast.sucesso("Entrega cadastrada");
      }
      onFechar();
      onSalvo();
    } catch (e) {
      console.error("Falha ao salvar entrega", e);
      setErro(mensagemDeErro(e, "Não foi possível salvar a entrega."));
    } finally {
      setSalvando(false);
    }
  }

  return (
    <Modal
      aberto={Boolean(alvo)}
      titulo={editando ? "Editar entrega" : "Nova entrega"}
      descricao={editando ? alvo.recipient_name || alvo.address : "O que precisa ser entregue."}
      onFechar={onFechar}
      tamanho="lg"
    >
      <form className="form-modal" onSubmit={enviar} noValidate>
        {erro && <Alert tom="erro">{erro}</Alert>}

        {travada && (
          <Alert tom="atencao" titulo="Esta entrega já está em rota">
            Peso, endereço, data e janela de horário não podem mais ser
            alterados — eles foram usados para escolher o veículo e montar a
            sequência. Cancele a rota para reabri-la.
          </Alert>
        )}

        <SelectField
          label="Cliente cadastrado"
          value={form.customer_id}
          onChange={alterar("customer_id")}
          ajuda="Opcional. Preenche endereço e contato a partir do cadastro."
          disabled={travada}
        >
          <option value="">Venda avulsa (sem cadastro)</option>
          {clientes.map((c) => (
            <option value={String(c.id)} key={c.id}>
              {c.name}
            </option>
          ))}
        </SelectField>

        {travada ? (
          <InputField
            label="Endereço de entrega"
            value={endereco.address ?? ""}
            disabled
            ajuda="Não pode ser alterado com a entrega em rota."
          />
        ) : (
          <>
            <span className="rotulo-secao">Endereço de entrega</span>
            <CampoEndereco
              key={alvo?.id ?? "nova"}
              valor={endereco}
              aoMudar={setEndereco}
            />
          </>
        )}

        <div className="form-grade">
          <InputField
            label="Quem recebe"
            value={form.recipient_name}
            onChange={alterar("recipient_name")}
          />
          <InputField
            label="Telefone"
            value={form.recipient_phone}
            onChange={alterar("recipient_phone")}
          />
        </div>

        <InputField
          label="O que será entregue"
          placeholder="Guarda-roupa 6 portas, corrimão 4 m"
          value={form.description}
          onChange={alterar("description")}
        />

        <div className="form-grade">
          <InputField
            label="Data da entrega"
            type="date"
            value={form.scheduled_date}
            onChange={alterar("scheduled_date")}
            required
            obrigatorio
            disabled={travada}
          />
          <SelectField
            label="Prioridade"
            value={form.priority}
            onChange={alterar("priority")}
          >
            {Object.entries(PRIORIDADES).map(([valor, { rotulo }]) => (
              <option value={valor} key={valor}>
                {rotulo}
              </option>
            ))}
          </SelectField>
          <InputField
            label="Janela — início"
            type="time"
            value={form.time_window_start}
            onChange={alterar("time_window_start")}
            disabled={travada}
          />
          <InputField
            label="Janela — fim"
            type="time"
            value={form.time_window_end}
            onChange={alterar("time_window_end")}
            disabled={travada}
          />
        </div>

        <Alert tom="info" titulo="Preencha só o que a operação usa">
          Estes campos só viram restrição no cálculo quando o veículo também
          tiver o limite correspondente. Vazios são ignorados.
        </Alert>

        <div className="form-grade">
          <InputField
            label="Peso (kg)"
            type="number"
            min="0"
            step="0.01"
            value={form.weight_kg}
            onChange={alterar("weight_kg")}
            disabled={travada}
          />
          <InputField
            label="Volume (m³)"
            type="number"
            min="0"
            step="0.001"
            value={form.volume_m3}
            onChange={alterar("volume_m3")}
            disabled={travada}
          />
          <InputField
            label="Maior peça (m)"
            type="number"
            min="0"
            step="0.01"
            value={form.length_m}
            onChange={alterar("length_m")}
            disabled={travada}
          />
          <InputField
            label="Pessoas necessárias"
            type="number"
            min="1"
            max="20"
            value={form.required_crew}
            onChange={alterar("required_crew")}
            disabled={travada}
          />
        </div>

        <InputField
          label="Tempo no local (minutos)"
          type="number"
          min="1"
          value={form.service_time_minutes}
          onChange={alterar("service_time_minutes")}
          ajuda="Vazio usa o padrão da empresa. É o parâmetro que mais pesa no planejamento."
          disabled={travada}
        />

        <div className="form-grade">
          <InputField
            label="Número do pedido"
            value={form.order_number}
            onChange={alterar("order_number")}
          />
        </div>

        <TextareaField
          label="Observações"
          placeholder="Ponto de referência, cuidados no acesso"
          value={form.notes}
          onChange={alterar("notes")}
        />

        <div className="acoes-direita">
          <Button variante="secundario" onClick={onFechar}>
            Cancelar
          </Button>
          <Button type="submit" carregando={salvando}>
            {editando ? "Salvar alterações" : "Cadastrar entrega"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

/**
 * Histórico de uma entrega.
 *
 * É o registro append-only de cada mudança de status — com hora, motivo,
 * quem registrou e, quando o aparelho permitiu, a coordenada. É isto que a
 * empresa usa para responder "por que não foi entregue".
 */
export function ModalHistorico({ entrega, onFechar }) {
  const [eventos, setEventos] = useState(null);
  const [erro, setErro] = useState("");

  useEffect(() => {
    if (!entrega) {
      setEventos(null);
      return;
    }
    setErro("");
    api
      .historico(entrega.id)
      .then(setEventos)
      .catch((e) => {
        console.error("Falha ao carregar histórico", e);
        setErro(mensagemDeErro(e, "Não foi possível carregar o histórico."));
      });
  }, [entrega]);

  const motivo = (codigo) =>
    MOTIVOS_INSUCESSO.find((m) => m.valor === codigo)?.rotulo ?? codigo;

  return (
    <Modal
      aberto={Boolean(entrega)}
      titulo="Histórico da entrega"
      descricao={entrega?.recipient_name || entrega?.address}
      onFechar={onFechar}
    >
      {erro && <Alert tom="erro">{erro}</Alert>}

      {!eventos && !erro && <SkeletonText linhas={5} />}

      {eventos?.length === 0 && <p className="texto-3">Nenhum registro ainda.</p>}

      {eventos?.length > 0 && (
        <ol className="historico">
          {eventos.map((evento) => (
            <li className="historico__item" key={evento.id}>
              <div className="historico__marca" aria-hidden="true" />
              <div className="historico__conteudo">
                <div className="historico__topo">
                  <StatusBadge tipo="entrega" valor={evento.to_status} />
                  <span className="historico__quando">{dataHora(evento.created_at)}</span>
                </div>
                {evento.reason && (
                  <p className="historico__motivo">{motivo(evento.reason)}</p>
                )}
                {evento.notes && <p className="historico__nota">{evento.notes}</p>}
                {evento.latitude && (
                  <p className="historico__coordenada numero">
                    {Number(evento.latitude).toFixed(5)},{" "}
                    {Number(evento.longitude).toFixed(5)}
                  </p>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
    </Modal>
  );
}
