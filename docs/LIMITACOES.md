# Limitações conhecidas

Este documento existe para que ninguém — nem a equipe, nem um desenvolvedor futuro, nem quem
usa o sistema — confunda o que o Log Rotas **faz** com o que ele ainda **não faz**.

A regra do projeto: quando houver limitação, ela aparece aqui, no código e na tela. Nenhum
número estimado é apresentado como medido, e nenhuma ordenação simples é chamada de
"otimização".

**O fluxo completo funciona.** O que segue é o que precisa ser resolvido antes de a empresa
depender do sistema no dia a dia.

---

## 1. Antes de colocar em produção

Em ordem de urgência.

### 1.1 Provedores externos gratuitos não cobrem uso comercial

| Serviço | Para quê | Limite | O que fazer |
|---|---|---|---|
| **Nominatim** | Geocodificação | 1 requisição/s, uso pesado proibido | Plano pago, LocationIQ ou Google |
| **OSRM público** | Distância e tempo | Servidor de demonstração, sem garantia | OSRM próprio na VPS com extrato de MS |
| **Esri** | Ladrilhos do mapa | Uso comercial pede conta ArcGIS | CARTO, MapTiler ou Stadia (todos com chave) |
| **ViaCEP** | Consulta de CEP | Sem limite documentado | — |

Nenhum deles custa nada hoje e todos funcionam para desenvolvimento. Todos são trocáveis por
configuração: o código fala com `GeocodingProvider` e `MatrixProvider`, nunca com o serviço, e
a base cartográfica sai de `VITE_MAP_TILE_URL` no `.env` do frontend.

**Uma armadilha que já nos pegou:** a base era da CARTO, que passou a exigir chave. Ela não
recusa a requisição — devolve **HTTP 200 com um PNG válido**, carimbado com "API KEY
REQUIRED" atravessando o ladrilho. Nenhuma verificação automática de status detecta isso; só
olhando o mapa. Quando trocar de provedor, **confira visualmente**, não pelo código de
resposta.

**Quando o OSRM sai do ar**, o sistema cai para estimativa em linha reta e **avisa na tela** —
o planejamento continua possível, mas os quilômetros deixam de ser de estrada.

### 1.2 Geolocalização do motorista exige HTTPS

`navigator.geolocation` só funciona em contexto seguro. `http://localhost` conta;
`http://192.168.x.x` **não**. Abrir a aplicação no celular pela rede local, por IP, não dá
acesso à localização.

O sistema não trava por isso — a coordenada é opcional em todo registro, e o motorista
consegue trabalhar sem ela. Mas o registro fica sem a prova de onde ele estava.

Resolver com HTTPS na VPS, ou túnel durante o desenvolvimento.

### 1.3 Sem limite de tentativas de login

Não há bloqueio por tentativas repetidas nem CAPTCHA. Em rede interna o risco é baixo; ao
publicar na internet isso precisa entrar — preferencialmente no nginx, não na aplicação.

O login já não revela quais e-mails existem: senha errada e e-mail inexistente devolvem a
mesma mensagem, no mesmo tempo.

### 1.4 Verificação de e-mail desligada

A coluna `users.email_verified` existe, mas não é exigida — montar SMTP travaria o primeiro
acesso. Como não há cadastro público, o risco é baixo. Reavaliar se o sistema for exposto
para fora da empresa.

### 1.5 Tokens em `localStorage`

Expõe a XSS. A alternativa (cookie `httpOnly`) dificultaria o aplicativo nativo previsto.
Mitigações: token de 60 min, revogação imediata por `token_version`, nenhum HTML injetado sem
escape.

---

## 2. Números que ainda são estimativa

Estes valores entraram como suposição e precisam ser calibrados com a operação real.

| Parâmetro | Valor | Onde muda |
|---|---|---|
| Tempo padrão por parada | 60 min | Configurações, na interface |
| Tempo fixo de estacionar | 5 min | `stop_grouping.TEMPO_BASE_PARADA_S` |
| Fator de correção da linha reta | 1,35 | `haversine.FATOR_RUA` |
| Velocidade média urbana | 28 km/h | `haversine.VELOCIDADE_KMH` |
| Jornada padrão | 8 h | `contracts.VeiculoDisponivel` |

Os três últimos só entram em jogo quando o OSRM está fora — com ele, distância e tempo são
medidos na malha viária.

**O tempo de parada é o que mais pesa.** A operação é dentro de Campo Grande, com
deslocamentos de 10 a 25 minutos. Se a entrega inclui instalação, o tempo de serviço domina o
de estrada em ordem de grandeza — e o que limita o dia da equipe é quantos serviços cabem
nele, não quanto ela roda. É por isso que o otimizador minimiza **tempo**, não quilometragem.

### Perguntas ainda abertas sobre a operação

O sistema foi construído para que errar essas respostas custe barato: todo campo de medida é
opcional e só vira restrição quando preenchido dos dois lados — na entrega e no veículo.

1. O que limita a carga: peso, volume ou comprimento?
2. A entrega inclui instalação? Quanto tempo leva, do mais rápido ao mais demorado?
3. Quantas pessoas cada tipo de serviço exige?
4. Quantas entregas saem num dia normal e num dia cheio?
5. Existe compromisso de horário com o cliente?
6. O endereço chega junto com um número de pedido ou nota?

---

## 3. Decisões de escopo

### 3.1 Uma viagem por rota

O MVP gera `BASE_SAIDA → ENTREGA* → BASE_RETORNO`. Voltar à base no meio do dia para
recarregar **não** está implementado.

O modelo já comporta: `route_stops` tem `stop_type` (com `BASE_RECARGA`) e `trip_number`.
Implementar é trabalho no solver, não migração destrutiva na tabela que mais terá linhas.

### 3.2 Janela de horário

Respeitada pelo solver quando preenchida. Não é obrigatória, e a maioria das entregas não vai
ter — o que é o comportamento certo enquanto não se sabe se a Britto agenda horário.

### 3.3 Prioridade influencia, não determina

A prioridade vira penalidade de dispensa: o solver sacrifica uma entrega `BAIXA` antes de uma
`URGENTE` quando não cabe tudo. Ela **não** força uma entrega a ser a primeira da rota.

### 3.4 Aplicação de empresa única

Sem multi-tenancy. Reverter é migration mecânica (adicionar `company_id`, preencher com 1,
criar índices, ajustar repositórios) — um a dois dias.

### 3.5 Polling, não WebSocket

O painel atualiza a cada 15 segundos. Suficiente para poucos motoristas; vira SSE quando
houver GPS contínuo.

### 3.6 Endereço: CEP é o caminho principal, não o texto livre

O cadastro começa pelo CEP porque endereço brasileiro digitado por extenso é a pior entrada
possível para geocodificação — "Av. Calógeras 1500" tem dezenas de grafias. O ViaCEP devolve
logradouro, bairro, cidade e UF normalizados, e o endereço montado a partir disso acerta
muito mais.

O campo de texto livre continua ali para quem não sabe o CEP, com aviso de que o resultado
costuma ser menos preciso.

**Limite conhecido:** o Nominatim frequentemente resolve o endereço no nível da RUA, não do
número. O pino cai na via certa, podendo estar algumas dezenas de metros fora. A interface
avisa quando isso acontece e o pino é arrastável — o ajuste manual vira `MANUAL` e não é mais
sobrescrito. Um provedor pago resolveria no número, e é a primeira troca que vale o dinheiro.

**O pino não é instantâneo.** Medido no navegador, em endereços de Campo Grande nunca
consultados antes: **3,8 s e 5,6 s** entre a última tecla e o pino no mapa. Desse tempo,
0,9 s é a espera deliberada do debounce e o resto é o Nominatim. Endereço já consultado
antes responde do cache em menos de 1 s.

O comportamento é o do Google Maps — digitou, achou, sem clicar em nada — mas a resposta
leva alguns segundos, e é por isso que a tela mostra "Localizando no mapa..." em vez de
ficar parada. Encurtar o debounce não ajuda: o gargalo é o provedor, que permite uma
consulta por segundo. Quem quiser a resposta instantânea troca o provedor, não o código —
o `GeocodingProvider` existe para isso.

### 3.7 Limitador de taxa em memória

O limite de 1 req/s do Nominatim é respeitado por um lock de processo. Com vários workers isso
deixa de valer, e o controle passa a ser assunto de fila externa.

---

## 4. O que o sistema se recusa a fazer

Estas recusas são deliberadas. Cada uma protege contra um erro que só apareceria tarde demais.

| Situação | O sistema faz | Em vez de |
|---|---|---|
| Endereço com vários resultados possíveis | Manda para revisão humana | Escolher o primeiro |
| Entrega sem coordenada no planejamento | Recusa o cálculo, com a lista | Ignorar em silêncio |
| Carga acima da capacidade | Deixa de fora e reporta | Espremer no veículo |
| Solver sem solução | Diz o motivo | Devolver ordenação por proximidade |
| Rota finalizada com entrega sem registro | Marca como **não entregue** | Dar por entregue |
| Endereço alterado | Descarta a coordenada antiga | Manter o pino no lugar anterior |
| Confirmar planejamento duas vezes | Recusa a segunda | Gravar tudo de novo |
| Matriz vinda do fallback | Avisa na tela que é estimativa | Apresentar como distância real |
| Entrega já em rota | Trava peso, endereço e data | Deixar alterar e invalidar a rota |

### Acessibilidade verificada por medição

A escala de texto foi calibrada calculando a razão de contraste de cada nível contra a
superfície mais clara em que aparece, nos dois temas. Os quatro níveis atingem 4.5:1 (WCAG AA
para texto pequeno). O nível mais apagado reprovava com 2.6:1 na primeira versão e foi
escurecido.
