# Limitações conhecidas

Este documento existe para que ninguém — nem a equipe, nem um desenvolvedor futuro, nem quem
usa o sistema — confunda o que o Log Rotas **faz** com o que ele ainda **não faz**.

A regra do projeto: quando houver limitação, ela aparece aqui, no código e na tela. Nenhum
número estimado é apresentado como medido, e nenhuma ordenação simples é chamada de
"otimização".

Última atualização: **Fase 2**.

---

## 1. O que ainda não existe

| Funcionalidade | Fase prevista |
|---|---|
| Cadastro de clientes, motoristas, veículos e bases | 3 |
| Cadastro de entregas | 3 |
| Geocodificação de endereços | 4 |
| Mapa da operação (Leaflet + OpenStreetMap) | 4 |
| Distância e duração reais entre paradas | 5 |
| Agrupamento de entregas em paradas | 6 |
| Otimização de rotas (OR-Tools) | 6 |
| Planejador: calcular, revisar, confirmar | 7 |
| Indicadores operacionais no painel | 8 |
| Aplicação do motorista no celular | 9 |

O painel administrativo mostra o andamento da implantação em vez de indicadores, e a tela do
motorista diz que não há rota atribuída. Isso é intencional: uma tela com números de exemplo
ensina a equipe a confiar em dado que não existe.

---

## 2. Decisões tomadas sobre suposições, não sobre dados

Estes valores entraram no sistema como **estimativa** e precisam ser calibrados com a
operação real da Britto. Enquanto não forem, qualquer cálculo que dependa deles é aproximado.

| Parâmetro | Valor atual | Situação |
|---|---|---|
| Tempo padrão por parada | 60 min | **Chute.** Editável em Configurações |
| Restrição principal de carga | comprimento (suposto) | Não confirmado |
| Entrega inclui instalação | provavelmente sim | Não confirmado |
| Equipe por entrega | até 4 pessoas | Informado, ainda não modelado |
| Volume diário de entregas | desconhecido | Sistema dimensionado para dezenas/dia |
| Vínculo com pedido / nota fiscal | desconhecido | Campos opcionais previstos |

**Por que o tempo de parada importa tanto:** a operação é dentro de Campo Grande, com
deslocamentos de 10 a 25 minutos entre paradas. Se a instalação leva 90 minutos, o tempo de
serviço domina o tempo de estrada em ordem de grandeza — e o que limita o dia da equipe não é
a distância, é quantos serviços cabem nele. Por isso a dimensão principal do otimizador será
**tempo**, não quilometragem.

Perguntas a levar a quem carrega o caminhão estão registradas no histórico do projeto e devem
ser respondidas antes da Fase 6.

---

## 3. Segurança: riscos aceitos conscientemente

### 3.1 Tokens em `localStorage`

Os tokens ficam em `localStorage`, o que os expõe a XSS. A alternativa (cookie `httpOnly`)
dificultaria o aplicativo nativo previsto mais adiante.

Mitigações em vigor: token de acesso curto (60 min), revogação imediata por `token_version`
no backend (troca de senha, desativação de usuário e redefinição de senha derrubam todas as
sessões), e nenhum HTML injetado sem escape no frontend.

### 3.2 Verificação de e-mail desligada

A coluna `users.email_verified` existe desde a primeira migration, mas a verificação não é
exigida. Exigir confirmação por e-mail sem servidor SMTP configurado travaria o primeiro
acesso, e montar SMTP agora seria infraestrutura desnecessária para uso interno.

Como o sistema não tem cadastro público, o risco é baixo: só o administrador cria usuários.
**Precisa ser reavaliado** se o sistema um dia for exposto para fora da empresa.

### 3.3 Acessibilidade verificada por medição

A escala de texto da interface foi calibrada calculando a razão de contraste de cada nível
contra a superfície mais clara em que ele aparece, nos dois temas. Os quatro níveis atingem
4.5:1 (mínimo da WCAG AA para texto pequeno). O nível mais apagado, usado em e-mail de
tabela e contexto de indicador, reprovava com 2.6:1 na primeira versão da paleta e foi
escurecido.

A hierarquia entre os níveis passou a se apoiar também em tamanho e peso, não apenas em
cor — empilhar cinzas cada vez mais claros termina com o último ilegível.

### 3.4 Sem limite de tentativas de login

Não há bloqueio por tentativas repetidas nem CAPTCHA. Em rede interna o risco é baixo; ao
publicar o sistema na internet, isso precisa entrar — preferencialmente no nginx, não na
aplicação.

O login já não revela quais e-mails existem: senha errada e e-mail inexistente devolvem a
mesma mensagem, no mesmo tempo (há um cálculo de hash descartável para igualar a duração da
resposta).

---

## 4. Limitações técnicas do ambiente

### 4.1 Geolocalização no celular exige HTTPS

`navigator.geolocation` só funciona em contexto seguro. `http://localhost` conta como seguro;
`http://192.168.x.x` **não**. Ou seja: abrir a aplicação no celular pela rede local, por IP,
**não vai** dar acesso à localização do motorista.

Isso precisa ser resolvido antes da Fase 9. Opções: túnel HTTPS durante o desenvolvimento, ou
subir o sistema em uma VPS com certificado.

### 4.2 Provedores externos gratuitos têm limite (Fases 4 e 5)

- **Nominatim** (geocodificação): 1 requisição por segundo, `User-Agent` obrigatório, uso
  pesado proibido. Mitigação planejada: cache em banco e fila serializada.
- **OSRM público** (distância/tempo): servidor de demonstração, sem garantia de
  disponibilidade e proibido para uso comercial de volume. Mitigação planejada: OSRM próprio
  na VPS, com o extrato de Mato Grosso do Sul.
- **Base cartográfica (CARTO)**: o painel usa os ladrilhos gratuitos `light_all` /
  `dark_all` da CARTO, servidos sobre dados do OpenStreetMap. São adequados a
  desenvolvimento e uso leve, mas a política do serviço não cobre aplicação comercial de
  volume. Antes de a empresa depender do sistema, trocar por um plano pago da CARTO, por
  MapTiler ou por Stadia — é uma URL no componente `MapPanel`, nada além disso.
  A atribuição ao OpenStreetMap e à CARTO já é exibida no mapa, como a licença exige.

Nada disso impede o desenvolvimento local nem custa dinheiro agora, mas todos precisam ser
trocados antes de a empresa depender do sistema no dia a dia.

### 4.3 Cobertura de endereços em Campo Grande

O Nominatim tem cobertura irregular em loteamento novo, chácara e endereço sem número. A
operação ser numa cidade só ajuda: os endereços se repetem entre pedidos e o cache acerta com
o tempo, e o administrador poderá corrigir o pino no mapa uma vez para sempre.

Primeira evolução prevista: aceitar CEP + número via ViaCEP, bem mais confiável no Brasil do
que endereço por extenso.

---

## 5. Escolhas de arquitetura que restringem o futuro

| Escolha | Consequência | Custo para reverter |
|---|---|---|
| Aplicação de empresa única (sem multi-tenancy) | Não atende duas empresas | Migration mecânica: adicionar `company_id`, preencher com 1, criar índices, ajustar repositórios — 1 a 2 dias |
| Chaves primárias `BIGINT` sequenciais | IDs previsíveis em URL | Aceitável: o sistema é interno e autenticado |
| SQLAlchemy síncrono | Menor throughput teórico | Irrelevante neste volume; reversível |
| Polling em vez de WebSocket | Painel atualiza a cada ~10s | Suficiente para 4 motoristas; vira SSE quando houver GPS contínuo |

---

## 6. O que este documento promete

Toda funcionalidade que for entregue com limitação relevante entra aqui **e** aparece na
interface. Especificamente, quando a otimização existir:

- se a matriz de distância vier do fallback em linha reta, a tela dirá
  **"distância estimada em linha reta — não é distância de estrada"**;
- se o solver não encontrar solução, o sistema dirá o motivo (ex.: demanda acima da
  capacidade disponível) em vez de devolver uma ordenação qualquer;
- entregas que não couberem na frota voltam como não atribuídas e continuam pendentes,
  visíveis na tela.
