/**
 * O roteiro do tutorial guiado.
 *
 * A ordem é a do dia de trabalho, não a do menu: cadastrar o que sai, montar
 * as rotas, acompanhar, conferir depois. Cada passo é uma frase — quem está
 * aprendendo não lê parágrafo com a tela escurecida atrás.
 *
 * `alvo` é um seletor da tela de verdade. Os pontos importantes carregam
 * `data-tour` justamente para o tutorial não depender de classe de estilo,
 * que muda quando alguém mexe no visual.
 */

export const PASSOS_ADMIN = [
  {
    titulo: "Bem-vindo ao Log Rotas",
    texto:
      "Em um minuto eu mostro o caminho de uma entrega: do cadastro até o caminhão na rua. Dá para sair a qualquer momento e ver de novo depois.",
  },
  {
    rota: "/admin/entregas",
    alvo: '[data-tour="nova-entrega"]',
    titulo: "1. Cadastre o que vai sair",
    texto:
      "Tudo começa aqui. Ao digitar o endereço, escolha uma das sugestões e confira o pino no mapa — é isso que leva o caminhão à porta certa.",
  },
  {
    rota: "/admin/planejamento",
    alvo: '[data-tour="opcoes-plano"]',
    titulo: "2. Diga como é o dia",
    texto:
      "Data, base e hora de saída. Deixe o trânsito marcado: sem ele os horários saem otimistas. Se a carga não cabe de uma vez, escolha 2 viagens.",
  },
  {
    rota: "/admin/planejamento",
    alvo: '[data-tour="calcular"]',
    titulo: "3. O sistema monta as rotas",
    texto:
      "Marque as entregas e os veículos, e clique aqui. Ele decide a ordem das paradas, respeitando jornada, capacidade e horário combinado com o cliente.",
  },
  {
    rota: "/admin/planejamento",
    titulo: "4. Revise antes de confirmar",
    texto:
      "Enquanto você não confirma, nada muda na operação. Confira as rotas, escolha o motorista de cada uma e confirme — só então elas aparecem no celular dele.",
  },
  {
    rota: "/admin",
    alvo: '[data-tour="painel-mapa"]',
    titulo: "5. Acompanhe o dia",
    texto:
      "Aqui você vê cada caminhão andando, a próxima parada e se está adiantado ou atrasado. Ele se move enquanto o motorista estiver com o aplicativo aberto.",
  },
  {
    rota: "/admin/relatorios",
    alvo: 'a[href="/admin/relatorios"]',
    titulo: "6. Depois da semana, confira",
    texto:
      "Quanto foi entregue, o que falhou e por quê — e se o tempo que o sistema reserva por entrega corresponde ao que a equipe leva de verdade.",
  },
  {
    alvo: '[data-tour="menu-usuario"]',
    titulo: "Pronto",
    texto:
      "Para rever este tutorial, clique no seu nome aqui e escolha Ver tutorial. Boa operação.",
  },
];

export const PASSOS_MOTORISTA = [
  {
    titulo: "Sua rota no celular",
    texto:
      "Vou mostrar em quatro passos como é o seu dia aqui dentro. Dá para rever depois pelo ícone de ajuda, em cima.",
  },
  {
    alvo: '[data-tour="rota-do-dia"]',
    titulo: "1. A rota de hoje",
    texto:
      "Suas rotas do dia aparecem aqui. Toque na rota para abrir a lista de paradas, na ordem em que você vai fazer.",
  },
  {
    titulo: "2. Saindo da base",
    texto:
      "Toque em INICIAR ROTA quando sair. A navegação abre sozinha, com voz, e a tela fica acesa. Mantenha o aplicativo na frente: é assim que o escritório vê onde você está.",
  },
  {
    titulo: "3. Em cada parada",
    texto:
      "Ao estacionar, toque em CHEGUEI. Depois de descarregar: ENTREGUE, e o nome de quem recebeu — ou NÃO ENTREGUE, e o motivo. O que não for registrado conta como não entregue.",
  },
  {
    titulo: "4. No fim do dia",
    texto:
      "De volta à base, toque em FINALIZAR ROTA. Se o dia tiver duas viagens, o aplicativo avisa para voltar, recarregar e sair de novo.",
  },
];
