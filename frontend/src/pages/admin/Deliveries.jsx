import { useCallback, useEffect, useState } from "react";
import { History, MapPinOff, MoreHorizontal, Package, Pencil, Plus, Search } from "lucide-react";

import { mensagemDeErro } from "../../api/client";
import { clientes as apiClientes } from "../../api/cadastros";
import { entregas as api } from "../../api/operacao";
import { GeocodeBadge } from "../../components/domain";
import {
  Alert,
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
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useToast } from "../../hooks/useToast";
import { PRIORIDADES, dataCurta, hoje, peso } from "../../utils/formato";
import { ModalEntrega, ModalHistorico } from "./DeliveryModals";
import "./admin.css";

const STATUS = [
  "PENDENTE",
  "PLANEJADA",
  "EM_ROTA",
  "CHEGOU",
  "ENTREGUE",
  "NAO_ENTREGUE",
  "CANCELADA",
];

export function Deliveries() {
  useDocumentTitle("Entregas");
  const toast = useToast();

  const [itens, setItens] = useState([]);
  const [clientes, setClientes] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  const [data, setData] = useState(hoje());
  const [status, setStatus] = useState("");
  const [prioridade, setPrioridade] = useState("");
  const [busca, setBusca] = useState("");
  const [soSemCoordenada, setSoSemCoordenada] = useState(false);

  const [modal, setModal] = useState(null);
  const [historico, setHistorico] = useState(null);

  const carregar = useCallback(async () => {
    setCarregando(true);
    setErro("");
    try {
      const filtros = {};
      if (data) filtros.data = data;
      if (status) filtros.status = [status];
      if (prioridade) filtros.priority = prioridade;
      if (busca.trim()) filtros.search = busca.trim();
      if (soSemCoordenada) filtros.sem_coordenada = true;
      setItens(await api.listar(filtros));
    } catch (e) {
      console.error("Falha ao listar entregas", e);
      setErro(mensagemDeErro(e, "Não foi possível carregar as entregas."));
    } finally {
      setCarregando(false);
    }
  }, [data, status, prioridade, busca, soSemCoordenada]);

  useEffect(() => {
    const id = setTimeout(carregar, busca ? 300 : 0);
    return () => clearTimeout(id);
  }, [carregar, busca]);

  useEffect(() => {
    apiClientes
      .listar({ active: true })
      .then(setClientes)
      .catch((e) => console.error("Falha ao listar clientes", e));
  }, []);

  async function cancelar(entrega) {
    try {
      await api.mudarStatus(entrega.id, { status: "CANCELADA" });
      toast.sucesso("Entrega cancelada");
      await carregar();
    } catch (e) {
      console.error("Falha ao cancelar entrega", e);
      toast.erro("Não foi possível cancelar", mensagemDeErro(e));
    }
  }

  const semCoordenada = itens.filter((e) => e.latitude === null).length;
  const temFiltro = Boolean(status || prioridade || busca.trim() || soSemCoordenada);

  return (
    <>
      <PageHeader
        titulo="Entregas"
        descricao="O que precisa sair. Só entrega com coordenada entra no planejamento."
        acoes={
          <Button icone={Plus} onClick={() => setModal("nova")} data-tour="nova-entrega">
            Nova entrega
          </Button>
        }
      />

      {!carregando && semCoordenada > 0 && (
        <Alert
          tom="atencao"
          titulo={`${semCoordenada} entrega(s) sem coordenada`}
          acao={
            <Button
              variante="secundario"
              tamanho="sm"
              onClick={() => setSoSemCoordenada(true)}
            >
              Ver só essas
            </Button>
          }
        >
          Elas não podem ser planejadas. Resolva os endereços em
          <strong> Endereços</strong> antes de calcular as rotas.
        </Alert>
      )}

      <Card semPadding>
        <div className="filtros">
          <div className="filtros__busca">
            <InputField
              label="Buscar"
              placeholder="Destinatário, endereço ou pedido"
              icone={Search}
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
          </div>

          <div className="filtros__campo">
            <InputField
              label="Data"
              type="date"
              value={data}
              onChange={(e) => setData(e.target.value)}
            />
          </div>

          <div className="filtros__campo">
            <SelectField
              label="Status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="">Todos</option>
              {STATUS.map((s) => (
                <option value={s} key={s}>
                  {s.replace("_", " ").toLowerCase()}
                </option>
              ))}
            </SelectField>
          </div>

          <div className="filtros__campo">
            <SelectField
              label="Prioridade"
              value={prioridade}
              onChange={(e) => setPrioridade(e.target.value)}
            >
              <option value="">Todas</option>
              {Object.entries(PRIORIDADES).map(([valor, { rotulo }]) => (
                <option value={valor} key={valor}>
                  {rotulo}
                </option>
              ))}
            </SelectField>
          </div>

          {!carregando && !erro && itens.length > 0 && (
            <span className="filtros__contagem numero">
              {itens.length} {itens.length === 1 ? "entrega" : "entregas"}
            </span>
          )}
        </div>

        {soSemCoordenada && (
          <div className="filtro-ativo">
            <MapPinOff size={14} strokeWidth={2} aria-hidden="true" />
            Mostrando apenas entregas sem coordenada
            <Button variante="texto" tamanho="sm" onClick={() => setSoSemCoordenada(false)}>
              limpar
            </Button>
          </div>
        )}

        {carregando && <SkeletonTable linhas={5} colunas={5} />}

        {!carregando && erro && (
          <ErrorState
            titulo="Não foi possível carregar as entregas"
            mensagem={erro}
            aoTentarNovamente={carregar}
          />
        )}

        {!carregando && !erro && itens.length === 0 && (
          <EmptyState
            icone={Package}
            titulo={temFiltro ? "Nada encontrado" : "Nenhuma entrega para esta data"}
            acao={
              temFiltro ? (
                <Button
                  variante="secundario"
                  onClick={() => {
                    setStatus("");
                    setPrioridade("");
                    setBusca("");
                    setSoSemCoordenada(false);
                  }}
                >
                  Limpar filtros
                </Button>
              ) : (
                <Button icone={Plus} onClick={() => setModal("nova")}>
                  Cadastrar entrega
                </Button>
              )
            }
          >
            <p>
              {temFiltro
                ? "Nenhuma entrega corresponde aos filtros selecionados."
                : "Cadastre as entregas do dia para poder montar as rotas."}
            </p>
          </EmptyState>
        )}

        {!carregando && !erro && itens.length > 0 && (
          <Table>
            <THead>
              <TH>Destino</TH>
              <TH largura="120px">Prioridade</TH>
              <TH largura="110px">Carga</TH>
              <TH largura="140px">Localização</TH>
              <TH largura="130px">Status</TH>
              <TH largura="60px">
                <span className="sr-apenas">Ações</span>
              </TH>
            </THead>
            <TBody>
              {itens.map((e) => (
                <TR key={e.id}>
                  <TD>
                    <span className="tb__principal">
                      {e.recipient_name || e.customer?.name || `Entrega ${e.id}`}
                    </span>
                    <span className="tb__secundario">
                      {e.address ?? "sem endereço"}
                      {e.order_number ? ` · pedido ${e.order_number}` : ""}
                      {e.scheduled_date !== data ? ` · ${dataCurta(e.scheduled_date)}` : ""}
                    </span>
                  </TD>

                  <TD>
                    <Badge tom={PRIORIDADES[e.priority]?.tom ?? "neutro"}>
                      {PRIORIDADES[e.priority]?.rotulo ?? e.priority}
                    </Badge>
                  </TD>

                  <TD>
                    {e.weight_kg ? (
                      <span className="numero">{peso(e.weight_kg)}</span>
                    ) : (
                      <span className="sem-dado">—</span>
                    )}
                  </TD>

                  <TD>
                    <GeocodeBadge status={e.geocode_status} semEndereco={!e.address} />
                  </TD>

                  <TD>
                    <StatusBadge tipo="entrega" valor={e.status} />
                  </TD>

                  <TDAcoes>
                    <Dropdown
                      gatilho={
                        <Button
                          variante="sutil"
                          tamanho="sm"
                          icone={MoreHorizontal}
                          aria-label={`Ações da entrega ${e.id}`}
                        />
                      }
                    >
                      <DropdownItem icone={Pencil} onClick={() => setModal(e)}>
                        Editar
                      </DropdownItem>
                      <DropdownItem icone={History} onClick={() => setHistorico(e)}>
                        Ver histórico
                      </DropdownItem>
                      <DropdownItem
                        icone={MapPinOff}
                        onClick={() => cancelar(e)}
                        disabled={!["PENDENTE", "PLANEJADA"].includes(e.status)}
                        perigo
                      >
                        Cancelar entrega
                      </DropdownItem>
                    </Dropdown>
                  </TDAcoes>
                </TR>
              ))}
            </TBody>
          </Table>
        )}
      </Card>

      <ModalEntrega
        alvo={modal}
        clientes={clientes}
        dataPadrao={data}
        onFechar={() => setModal(null)}
        onSalvo={carregar}
      />

      <ModalHistorico entrega={historico} onFechar={() => setHistorico(null)} />
    </>
  );
}
