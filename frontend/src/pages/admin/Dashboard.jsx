import { Alert, Badge, Card, PageHeader } from "../../components/ui";
import { useAuth } from "../../hooks/useAuth";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import "./admin.css";

/**
 * Painel administrativo.
 *
 * Os indicadores operacionais (entregas do dia, rotas em andamento, distancia
 * planejada) dependem de entregas e rotas, que entram nas Fases 3 e 7. Ate
 * la esta tela mostra o andamento da implantacao — e nao numeros inventados,
 * que ensinariam a equipe a confiar em dado que nao existe.
 */
const ETAPAS = [
  { nome: "Acesso, usuarios e permissoes", fase: "Fase 2", pronto: true },
  { nome: "Configuracao da empresa", fase: "Fase 2", pronto: true },
  { nome: "Cadastros: clientes, motoristas, veiculos, bases", fase: "Fase 3", pronto: false },
  { nome: "Entregas e geocodificacao dos enderecos", fase: "Fases 3 e 4", pronto: false },
  { nome: "Mapa da operacao", fase: "Fase 4", pronto: false },
  { nome: "Distancia e tempo reais entre paradas", fase: "Fase 5", pronto: false },
  { nome: "Otimizacao das rotas", fase: "Fase 6", pronto: false },
  { nome: "Planejador: calcular, revisar e confirmar", fase: "Fase 7", pronto: false },
  { nome: "Indicadores e mapa no painel", fase: "Fase 8", pronto: false },
  { nome: "Aplicacao do motorista no celular", fase: "Fase 9", pronto: false },
];

export function Dashboard() {
  useDocumentTitle("Painel");
  const { usuario } = useAuth();

  const concluidas = ETAPAS.filter((e) => e.pronto).length;

  return (
    <>
      <PageHeader
        titulo={`Bem-vindo, ${usuario?.name?.split(" ")[0] ?? ""}`}
        descricao="Log Rotas — planejamento e execucao de rotas de entrega."
      />

      <div className="grade grade--duas">
        <Card
          titulo="Andamento da implantacao"
          descricao={`${concluidas} de ${ETAPAS.length} etapas concluidas.`}
        >
          <ul className="etapas">
            {ETAPAS.map((etapa) => (
              <li
                key={etapa.nome}
                className={`etapa ${etapa.pronto ? "" : "etapa--pendente"}`}
              >
                <span className="etapa__nome">{etapa.nome}</span>
                <Badge tom={etapa.pronto ? "sucesso" : "neutro"}>
                  {etapa.pronto ? "Pronto" : etapa.fase}
                </Badge>
              </li>
            ))}
          </ul>
        </Card>

        <Card titulo="Proximos passos">
          <Alert tom="info" titulo="Ainda nao ha numeros para mostrar">
            Os indicadores do dia (entregas pendentes, rotas em andamento,
            distancia planejada) aparecem aqui quando existirem entregas
            cadastradas. Preferimos a tela vazia a numeros de exemplo.
          </Alert>

          <div style={{ marginTop: "var(--esp-4)" }} className="pilha">
            <p>O que ja da para fazer agora:</p>
            <ul style={{ paddingLeft: "var(--esp-5)" }}>
              <li>
                Conferir os dados da empresa em <strong>Configuracoes</strong>.
              </li>
              <li>
                Cadastrar os acessos da equipe em <strong>Usuarios</strong>,
                criando um login para cada motorista.
              </li>
            </ul>
          </div>
        </Card>
      </div>
    </>
  );
}
