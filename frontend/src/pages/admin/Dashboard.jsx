import { Check, CircleDashed, Package, PackageCheck, Route, Truck } from "lucide-react";

import { MapPanel } from "../../components/map/MapPanel";
import { Alert, Badge, Card, KpiCard, PageHeader } from "../../components/ui";
import { useAuth } from "../../hooks/useAuth";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";
import { useTheme } from "../../hooks/useTheme";
import "./admin.css";

/**
 * Painel administrativo.
 *
 * Os indicadores dependem de entregas e rotas, que entram nas Fases 3 e 7.
 * Até lá eles aparecem vazios, com a fase anotada — e não preenchidos com
 * número de exemplo. Dado falso numa tela de operação ensina a equipe a
 * confiar em algo que não existe, e o dia em que o número passar a ser real
 * ninguém vai perceber a diferença.
 */

const INDICADORES = [
  { rotulo: "Entregas hoje", icone: Package, tom: "marca", fase: "Fase 3" },
  { rotulo: "Em rota", icone: Truck, tom: "atencao", fase: "Fase 7" },
  { rotulo: "Concluídas", icone: PackageCheck, tom: "sucesso", fase: "Fase 9" },
  { rotulo: "Pendentes", icone: CircleDashed, tom: "info", fase: "Fase 3" },
];

const ETAPAS = [
  { nome: "Acesso, usuários e permissões", fase: "Fase 2", pronto: true },
  { nome: "Configuração da empresa", fase: "Fase 2", pronto: true },
  { nome: "Interface e sistema visual", fase: "Fase 2", pronto: true },
  { nome: "Clientes, motoristas, veículos e bases", fase: "Fase 3", pronto: false },
  { nome: "Entregas e geocodificação", fase: "Fases 3 e 4", pronto: false },
  { nome: "Entregas no mapa", fase: "Fase 4", pronto: false },
  { nome: "Distância e tempo reais", fase: "Fase 5", pronto: false },
  { nome: "Otimização das rotas", fase: "Fase 6", pronto: false },
  { nome: "Planejador de rotas", fase: "Fase 7", pronto: false },
  { nome: "Indicadores no painel", fase: "Fase 8", pronto: false },
  { nome: "Aplicação do motorista", fase: "Fase 9", pronto: false },
];

function saudacao() {
  const hora = new Date().getHours();
  if (hora < 12) return "Bom dia";
  if (hora < 18) return "Boa tarde";
  return "Boa noite";
}

function dataPorExtenso() {
  return new Intl.DateTimeFormat("pt-BR", {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());
}

export function Dashboard() {
  useDocumentTitle("Painel");
  const { usuario } = useAuth();
  const { tema } = useTheme();

  const primeiroNome = usuario?.name?.split(" ")[0] ?? "";
  const concluidas = ETAPAS.filter((e) => e.pronto).length;

  return (
    <>
      <PageHeader
        titulo={`${saudacao()}, ${primeiroNome}`}
        descricao={`${dataPorExtenso()} · Britto Móveis e Corrimão`}
      />

      <div className="kpis anima-lista">
        {INDICADORES.map((indicador) => (
          <KpiCard
            key={indicador.rotulo}
            rotulo={indicador.rotulo}
            valor="—"
            contexto={`Disponível na ${indicador.fase}`}
            icone={indicador.icone}
            tom={indicador.tom}
          />
        ))}
      </div>

      <Alert tom="info" titulo="Os indicadores ainda não têm de onde ler">
        Entregas e rotas entram nas Fases 3 e 7. Preferimos mostrar os campos
        vazios a preenchê-los com números de exemplo.
      </Alert>

      <div className="painel-grade">
        <Card
          titulo="Área de operação"
          descricao="Campo Grande, MS"
          semPadding
          className="painel-mapa"
        >
          <MapPanel
            tema={tema}
            altura={420}
            rodape={
              <div className="mapa-nota">
                Nenhuma entrega cadastrada. Quando a Fase 4 chegar, as entregas
                aparecem aqui como marcadores, e as rotas confirmadas como
                trajetos desenhados sobre a malha viária.
              </div>
            }
          />
        </Card>

        <Card
          titulo="Andamento da implantação"
          descricao={`${concluidas} de ${ETAPAS.length} etapas concluídas`}
          acoes={
            <Badge tom="marca">
              {Math.round((concluidas / ETAPAS.length) * 100)}%
            </Badge>
          }
        >
          <ol className="etapas">
            {ETAPAS.map((etapa) => (
              <li
                key={etapa.nome}
                className={`etapa ${etapa.pronto ? "etapa--pronta" : ""}`}
              >
                <span className="etapa__marca" aria-hidden="true">
                  {etapa.pronto && <Check size={11} strokeWidth={3} />}
                </span>
                <span className="etapa__nome">{etapa.nome}</span>
                <span className="etapa__fase">
                  {etapa.pronto ? "Pronto" : etapa.fase}
                </span>
              </li>
            ))}
          </ol>
        </Card>
      </div>

      <Card titulo="O que já dá para fazer" className="painel-proximos">
        <ul className="proximos">
          <li className="proximo">
            <span className="proximo__icone" aria-hidden="true">
              <Truck size={15} strokeWidth={2} />
            </span>
            <div>
              <strong>Cadastrar os acessos da equipe.</strong>
              <p>
                Cada motorista precisa de um login próprio para receber a rota no
                celular quando a Fase 9 chegar.
              </p>
            </div>
          </li>
          <li className="proximo">
            <span className="proximo__icone" aria-hidden="true">
              <Route size={15} strokeWidth={2} />
            </span>
            <div>
              <strong>Conferir os dados da empresa.</strong>
              <p>
                O tempo padrão por parada é o parâmetro que mais influencia o
                planejamento — e o valor atual ainda é uma estimativa.
              </p>
            </div>
          </li>
        </ul>
      </Card>
    </>
  );
}
