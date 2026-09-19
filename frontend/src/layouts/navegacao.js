import {
  BarChart3,
  Building2,
  LayoutDashboard,
  MapPin,
  MapPinned,
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
      { para: "/admin/entregas", rotulo: "Entregas", icone: Package },
      { para: "/admin/planejamento", rotulo: "Planejamento", icone: Waypoints },
      { para: "/admin/rotas", rotulo: "Rotas", icone: Route },
      { para: "/admin/enderecos", rotulo: "Endereços", icone: MapPinned },
    ],
  },
  {
    titulo: "Cadastros",
    itens: [
      { para: "/admin/clientes", rotulo: "Clientes", icone: Users },
      { para: "/admin/motoristas", rotulo: "Motoristas", icone: UserCog },
      { para: "/admin/veiculos", rotulo: "Veículos", icone: Truck },
      { para: "/admin/bases", rotulo: "Bases", icone: MapPin },
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
  "/admin/entregas": {
    titulo: "Entregas",
    contexto: "O que precisa sair",
  },
  "/admin/planejamento": {
    titulo: "Planejamento",
    contexto: "Calcular, revisar e confirmar as rotas do dia",
  },
  "/admin/rotas": {
    titulo: "Rotas",
    contexto: "O que foi planejado e o que aconteceu",
  },
  "/admin/enderecos": {
    titulo: "Endereços",
    contexto: "Endereços que ainda não viraram coordenada",
  },
  "/admin/clientes": {
    titulo: "Clientes",
    contexto: "Quem recebe as entregas",
  },
  "/admin/motoristas": {
    titulo: "Motoristas",
    contexto: "Quem executa as rotas",
  },
  "/admin/veiculos": {
    titulo: "Veículos",
    contexto: "A frota disponível para o planejamento",
  },
  "/admin/bases": {
    titulo: "Bases",
    contexto: "De onde as rotas saem e para onde voltam",
  },
  "/admin/configuracoes": {
    titulo: "Configurações",
    contexto: "Dados da empresa e parâmetros de planejamento",
  },
};
