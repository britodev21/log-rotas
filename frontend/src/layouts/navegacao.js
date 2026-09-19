import {
  BarChart3,
  Building2,
  LayoutDashboard,
  MapPin,
  Package,
  Route,
  Settings,
  Truck,
  UserCog,
  Users,
  Waypoints,
} from "lucide-react";

/**
 * Definição única da navegação administrativa.
 *
 * `fase` presente significa que a tela ainda não existe. O item continua
 * visível, mas desabilitado e com a fase em que entra — é mais honesto do
 * que escondê-lo (a equipe sabe o que vem) e do que deixá-lo clicável para
 * uma tela vazia (o que pareceria defeito).
 */
export const GRUPOS = [
  {
    titulo: "Operação",
    itens: [
      { para: "/admin", rotulo: "Painel", icone: LayoutDashboard, fim: true },
      { rotulo: "Entregas", icone: Package, fase: "F3" },
      { rotulo: "Planejamento", icone: Waypoints, fase: "F7" },
      { rotulo: "Rotas", icone: Route, fase: "F7" },
    ],
  },
  {
    titulo: "Cadastros",
    itens: [
      { rotulo: "Clientes", icone: Users, fase: "F3" },
      { rotulo: "Motoristas", icone: UserCog, fase: "F3" },
      { rotulo: "Veículos", icone: Truck, fase: "F3" },
      { rotulo: "Bases", icone: MapPin, fase: "F3" },
    ],
  },
  {
    titulo: "Sistema",
    itens: [
      { rotulo: "Relatórios", icone: BarChart3, fase: "F8" },
      { para: "/admin/usuarios", rotulo: "Usuários", icone: Building2 },
      { para: "/admin/configuracoes", rotulo: "Configurações", icone: Settings },
    ],
  },
];

/** Título e contexto que a topbar mostra para cada rota disponível. */
export const CONTEXTO_ROTA = {
  "/admin": { titulo: "Painel", contexto: "Visão geral da operação" },
  "/admin/usuarios": { titulo: "Usuários", contexto: "Quem tem acesso ao sistema" },
  "/admin/configuracoes": {
    titulo: "Configurações",
    contexto: "Dados da empresa e parâmetros de planejamento",
  },
};
