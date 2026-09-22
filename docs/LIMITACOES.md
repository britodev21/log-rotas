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

**Com o rastreamento ao vivo, isto deixou de ser detalhe:** sem HTTPS não há caminhão no
painel nem navegação. A tela do motorista diz isso ("GPS bloqueado: o sistema precisa ser
aberto por HTTPS") em vez de simplesmente não funcionar. Para testar no celular antes da VPS,
é preciso um túnel com HTTPS.

Resolver com HTTPS na VPS, ou túnel durante o desenvolvimento.

### 1.3 Limite de tentativas de login — resolvido

Existe desde 22/09/2026: 5 falhas numa conta ou 20 do mesmo IP em 15 min bloqueiam por 15 min,
inclusive para e-mail que não existe. Regras e decisões em `docs/SEGURANCA.md`.

**O que falta para produção:** o uvicorn atrás do nginx precisa de `--proxy-headers`, senão todo
login parece vir do IP do nginx e 20 erros de qualquer pessoa bloqueiam todo mundo.

### 1.4 Verificação de e-mail desligada

A coluna `users.email_verified` existe, mas não é exigida — montar SMTP travaria o primeiro
acesso. Como não há cadastro público, o risco é baixo. Reavaliar se o sistema for exposto
para fora da empresa.

### 1.5 Tokens em `localStorage`

Expõe a XSS. A alternativa (cookie `httpOnly`) dificultaria o aplicativo nativo previsto.
Mitigações: token de 60 min, revogação imediata por `token_version`, nenhum HTML injetado sem
escape — e, desde 22/09/2026, **Content-Security-Policy estrita** no build de produção, que impede
script de fora de rodar na página (`docs/SEGURANCA.md`). O nginx precisa enviá-la em produção.

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

**Quem calibra é o relatório.** A tela de Relatórios compara o tempo planejado com o medido em
duas frentes — o tempo parado na entrega e o deslocamento entre paradas, este separado por
fonte da matriz — e diz de quantas paradas o número saiu. Abaixo de 20 paradas ela avisa que
ainda não serve para mudar a configuração.

Duas coisas envenenariam essa medição, e ficam de fora com o motivo na tela:

- **Chegada e saída marcadas no mesmo minuto.** É o motorista registrando tudo de uma vez no
  fim da parada; entrando na conta, a mediana do tempo de parada despenca e o planejamento
  passa a prometer o impossível.
- **Parada concluída sem hora de chegada.** Fica fora da pontualidade, e o total delas aparece
  ao lado dos percentuais.

Enquanto o registro de chegada não for hábito na operação, a amostra é pequena — e a tela
mostra o tamanho dela justamente para ninguém decidir com três entregas.

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

### 3.1 Mais de uma viagem por dia

O planejamento aceita `max_viagens` (1 a 4) e `recarga_min`. Com mais de uma, a rota sai
`BASE_SAIDA → ENTREGA* → BASE_RECARGA → ENTREGA* → BASE_RETORNO`: o caminhão volta à base,
recarrega e sai de novo.

As regras, e por quê:

- **A viagem seguinte só sai depois de a anterior voltar mais o tempo de recarga.** No solver,
  cada viagem é um veículo próprio, e o relógio é um só — encadeados por restrição.
- **A jornada vale para o dia, não por viagem.** Duas viagens de 5 h não cabem numa jornada de
  8 h, e o plano deixa entregas de fora em vez de prometer um dia que não existe.
- **Cada viagem sai com o caminhão cheio:** a capacidade volta ao total depois da recarga. É o
  que torna a segunda viagem útil — é a carga que não cabia.
- **Viagem que não precisa não acontece.** Liberar 3 viagens não faz o caminhão voltar à base à
  toa: ele só volta quando a carga (ou o número de paradas) do dia não cabe de uma vez.
- **Carga que está na base não está no caminhão.** Ao iniciar a rota, só as entregas da viagem 1
  entram em `EM_ROTA`. As das viagens seguintes ficam `PLANEJADA` até o motorista registrar a
  recarga — senão o painel mostraria como "a caminho" o que ainda está no depósito.
- **A recarga só é concluída com as entregas da viagem anterior registradas.** O caminhão está
  na base, e a entrega que voltou precisa ser dita "não entregue", com motivo, em vez de sumir.

**O que ainda não existe:** preferência entre "menos caminhões" e "menos viagens". O
planejamento minimiza tempo total; se duas soluções empatam, ele não sabe que um caminhão a
menos economiza uma equipe no dia. Enquanto isso, quem decide é a seleção de veículos na tela.

### 3.2 Janela de horário

Respeitada pelo solver quando preenchida. Não é obrigatória, e a maioria das entregas não vai
ter — o que é o comportamento certo enquanto não se sabe se a Britto agenda horário.

**A janela vale para a CHEGADA do caminhão.** Até 21/09/2026 ela valia, por engano, para o
fim do serviço: o otimizador somava o tempo de serviço do destino em cada trecho, e o número
gravado como "chegada" era a hora em que a instalação terminava. Um cliente que recebe das 8h
às 10h, com instalação de 1 h, podia receber o caminhão às 7h; e toda chegada planejada saía
atrasada exatamente o tempo de serviço (entrega a 1 km da base prevista para 66 min depois da
saída). Corrigido e coberto por teste que falha no modelo antigo.

**O início do turno é hora de Campo Grande.** Até a mesma data, "08:00" era gravado como 08:00
UTC — 04:00 local —, e todo horário previsto saía quatro horas adiantado. **Planos calculados
antes da correção continuam com os horários errados**; recalcule os que ainda forem usados.

### 3.3 Prioridade influencia, não determina

A prioridade vira penalidade de dispensa: o solver sacrifica uma entrega `BAIXA` antes de uma
`URGENTE` quando não cabe tudo. Ela **não** força uma entrega a ser a primeira da rota.

### 3.4 Aplicação de empresa única

Sem multi-tenancy. Reverter é migration mecânica (adicionar `company_id`, preencher com 1,
criar índices, ajustar repositórios) — um a dois dias.

### 3.5 Polling, não WebSocket

Os indicadores do painel atualizam a cada 15 s; a posição dos caminhões, a cada 5 s. O celular
envia as posições a cada 10 s. Somando, **o caminhão no painel está de 10 a 15 s atrás da
realidade** — a tela mostra a idade ("posição de 12 s atrás"). O marcador desliza entre as
posições no ritmo em que o GPS as mediu, o que dá o movimento contínuo sem encurtar o atraso.

Para poucos caminhões, polling basta. SSE reduziria o atraso para ~10 s (o do envio do
celular) e é o próximo passo se isso importar.

### 3.8 Rastreamento e navegação numa página web

O GPS vem do navegador do celular, e o navegador **só entrega posição com a página na frente
e a tela acesa**. Consequências, todas assumidas:

- **A navegação é dentro do app.** Com o Google Maps na frente, a página ia para segundo plano
  e o GPS dela parava — o escritório perdia o caminhão justamente enquanto ele andava. O link
  do Google Maps continua, secundário, com o aviso "o acompanhamento pelo escritório pausa".
- **A tela fica acesa durante a rota** (Wake Lock). O motorista deve deixar o celular no
  carregador. Navegador que não suporta isso é avisado na tela.
- **Ligação, troca de app ou tela bloqueada pausam o rastreamento.** O que foi medido nesse
  tempo não existe; o que ficou na fila (sem internet) é enviado quando o sinal volta, até
  ~50 min de pontos.
- **Parado, muitos aparelhos param de dar leitura** — e computador sem GPS nunca dá. O app
  pede leitura nova a cada 15 s e, se nada novo entrar, reenvia a última posição a cada 20 s
  como **sinal de vida**, com a hora original. O servidor não grava repetido: só renova o
  contato. Assim o painel mostra "parado · posição de 2 min atrás", e não "sem sinal", num
  caminhão só parado. "Sem sinal" é reservado para 90 s sem contato nenhum.

Um aplicativo nativo com localização em segundo plano resolveria os três últimos. É outro
projeto, e só vale se as pausas incomodarem na prática.

**A navegação não tem** faixa de rolamento, radar nem desvio de congestionamento em tempo
real. O trajeto é o do OSRM (rua livre); o trânsito do Google corrige o **tempo** da previsão,
não o caminho.

**O ponto de chegada não é o pino.** O pino fica no lote, e a rua mais próxima dele pode ser a
de trás — medido: para "Rua Bahia, 500" a rota chegava pela Rua Piratininga, dando a volta no
quarteirão. Entre as ruas próximas, o sistema escolhe a do próprio endereço (até 80 m do
pino). Sem nome que bata, usa o pino.

**O mapa cinza da Esri só tem desenho até o zoom 16.** Acima disso a Esri devolve um ladrilho
"Map data not yet available" — com HTTP 200. O Leaflet amplia os ladrilhos do 16 para os zooms
17 a 19 (a navegação usa 17): menos nítido, mas é o mapa. O satélite tem imagem real até 19.

**Previsão de chegada:** deslocamento pela rua (OSRM) × fator de trânsito do Google + espera
pela janela do cliente + tempo de serviço, recalculada no máximo a cada 45 s por rota. Na
primeira medição, no mesmo trajeto, o OSRM previa 4 min e o Google com trânsito 7 min 53 s —
**o OSRM previa metade do tempo**. O fator corrige isso na previsão ao vivo, e o planejamento usa
o tempo do Google com o trânsito previsto (seção 3.10).

**Volume:** uma posição a cada ~10 s dá ~3.600 linhas por rota de 10 h. As posições com mais de
90 dias são apagadas pela limpeza automática (ver 3.9).

### 3.10 Trânsito no planejamento

Com `TRAFFIC_PROVIDER=google`, o tempo de cada trecho que o otimizador usa é o do Google, com o
trânsito previsto para o dia e a hora do turno. Como a matriz sai em poucas chamadas, o custo e o
que foi medido estão em `docs/SERVICOS_EXTERNOS.md`.

O que ele **não** faz:

- **Não muda o trânsito ao longo do dia dentro do plano.** A matriz é a da hora do turno (com a
  hora avançando dentro de cada chamada). Medido em Campo Grande: dentro do expediente o tempo
  varia ±3%, às 18h +7%. Um turno que atravessa o fim da tarde fica um pouco otimista no fim.
- **Não sabe que é caminhão.** O tempo é de carro.
- **Não prevê o passado.** Planejar um turno que já começou usa o trânsito de agora — a tela diz.
- **Sem o Google** (sem chave, fora do ar, cota acabou), o plano sai com a rua livre e diz por quê.
  Nunca um plano com metade dos trechos medidos apresentado como se todos fossem.

### 3.9 Limpeza automática

Todo dia, a partir das 3h de Campo Grande (`LIMPEZA_HORA`), o próprio servidor apaga o que passou
do prazo: posições do GPS (90 dias), tentativas de login (180), eventos de segurança (730),
endereços que falharam na busca (30 — para serem tentados de novo), as conferências de lugar do
Google (30 — só servem na hora de salvar a entrega) e os trechos com trânsito de dias que já
passaram. **Endereço encontrado não é apagado.**

- **"A partir das 3h", não "às 3h":** se o servidor estava desligado na hora, a limpeza roda
  quando ele voltar, no mesmo dia.
- **Uma vez por dia, mesmo com vários processos.** Cada processo tem o seu agendador; um
  bloqueio do PostgreSQL (advisory lock) e o registro em `maintenance_runs` impedem a
  execução em dobro. Conferido nos testes, com um segundo processo segurando o bloqueio.
- **Cada execução fica registrada** — quando, o que apagou, se falhou — e aparece em
  **Sistema → Segurança → Guarda dos dados**, onde também dá para limpar na hora.
- **Tudo numa transação.** Se falhar no meio, nada é apagado e a falha fica registrada; a
  execução do dia seguinte tenta de novo.

**Limite conhecido:** é uma thread dentro do servidor, não um agendador do sistema operacional.
Funciona igual em qualquer máquina sem configuração a mais, mas só roda com o servidor ligado. Se
o servidor passar dias desligado, a limpeza atrasada roda de uma vez na volta — o volume de
alguns dias é pequeno. Com a limpeza desligada (`LIMPEZA_HORA=-1`), use
`python -m app.tarefas limpar` num agendador externo.

### 3.6 Endereço: CEP é o caminho principal, não o texto livre

O cadastro começa pelo CEP porque endereço brasileiro digitado por extenso é a pior entrada
possível para geocodificação — "Av. Calógeras 1500" tem dezenas de grafias. O ViaCEP devolve
logradouro, bairro, cidade e UF normalizados, e o endereço montado a partir disso acerta
muito mais.

O campo de texto livre continua ali para quem não sabe o CEP, com aviso de que o resultado
costuma ser menos preciso.

### O número da porta não existe no OpenStreetMap de Campo Grande

Esta é a limitação mais séria do sistema, e ela não é de código.

Medido em 21/09/2026, via Overpass, na área urbana de Campo Grande:

| | |
|---|---|
| Ruas com nome | 13.864 |
| Prédios mapeados | 17.404 |
| **Prédios com número de porta** | **530** |

Numa cidade de cerca de 900 mil habitantes. Em oito endereços reais das avenidas principais,
com CEP conferido, o Nominatim resolveu o número em **zero** deles — testado com consulta de
texto livre **e** com consulta estruturada (`street`/`city`/`postalcode`), que é o formato
recomendado para casa e número.

**Consequência:** "Avenida Afonso Pena, 3000" vira um ponto qualquer de uma avenida de 10 km.

**O que isso descarta:** trocar o Nominatim por Photon, LocationIQ, MapTiler ou Stadia não
resolve. Todos leem o mesmo OpenStreetMap. O problema é o dado, não o provedor.

**O que o sistema faz a respeito**, em `app/services/precisao.py`:

- Coordenada só entra em rota se for `MANUAL` (alguém marcou no mapa) ou `EXATO` (o provedor
  resolveu no número do prédio). Precisão de rua, bairro ou cidade é **recusada** pelo
  planejamento, com a lista de quais endereços e por quê.
- A fila de Endereços lista exatamente o mesmo conjunto, pela mesma função. As duas regras
  vêm do mesmo arquivo de propósito: quando discordaram, o planejamento recusava registros
  que não apareciam em tela nenhuma.
- O CEP posiciona o mapa na quadra certa (o CEP brasileiro é por trecho de rua; em dez CEPs
  conferidos por geocodificação reversa, nove caem na rua correta), e o satélite da Esri
  permite ver o prédio. Confirmar leva segundos e é uma vez por endereço — cliente cadastrado
  propaga a confirmação para as próximas entregas.

**O custo honesto:** hoje, praticamente todo endereço novo exige um clique de confirmação.
Isso não é burocracia inventada; é o preço de não ter o dado.

### Busca com sugestões do Google (ligada)

Com `GOOGLE_MAPS_API_KEY` no `.env`, o cadastro de endereço vira o campo do Google Maps: a
pessoa digita, o Google sugere endereços que existem, ela escolhe um.

Medido em 21/09/2026, nos **mesmos oito endereços** em que o Nominatim acertou o número em
zero:

| | Nominatim | Google Places |
|---|---|---|
| Número certo em Campo Grande | 0 de 8 | **8 de 8** |

O pino do Nominatim ficava de **900 m a 2,3 km** do ponto do Google em sete dos oito.

**Achar o endereço não é provar o portão.** O Places diz onde fica o lugar, mas não se o ponto é
o telhado ou uma estimativa entre as casas da quadra. Quem diz é a Geocoding API
(`location_type`). Só `ROOFTOP` dispensa conferência — e quem decide isso é o **servidor**,
conferindo no próprio cache que a coordenada gravada é a mesma que o Google devolveu. O
navegador manda só o `place_id`; não consegue afirmar "é exato".

**A Geocoding API exige faturamento ativo** no projeto do Google — conferido em 21/09/2026:
ativada e liberada na chave, ela respondeu "You must enable Billing", enquanto a Places API
(New) funcionou sem faturamento. **Enquanto ela não responder**, nenhum ponto vira
exato: todo endereço escolhido pede um clique de conferência. O pino já começa no lugar certo,
então a conferência é um olhar no satélite e o botão "Conferi — o ponto está no portão".

**Tempo:** a primeira sugestão depois de o servidor subir leva ~2 s (abertura da conexão com o
Google); as seguintes, 250 a 700 ms. Antes de reaproveitar a conexão, **todas** levavam ~2 s —
o aperto de mão TLS a cada tecla.

**Custo:** o token de sessão agrupa a digitação e a escolha numa cobrança só. Ainda assim é
serviço pago por uso; ponha cota diária e alerta de orçamento no console.

### Trocar por um provedor que acha o número

Os adaptadores de **Google** e **HERE** já estão escritos (`app/geocoding/google.py` e
`here.py`). A troca é só configuração:

```
GEOCODING_PROVIDER=google      # ou here
GEOCODING_PROVIDER_KEY=<chave>
```

Os dois mantêm base própria de endereços e resolvem no número na maior parte do Brasil
urbano — a confirmação manual deixa de ser a regra e volta a ser a exceção.

Os dois pedem cartão no cadastro. A HERE tem cota diária gratuita, o que costuma bastar para
uma operação do tamanho da Britto; o Google tende a ter cobertura melhor no Brasil, e a
diferença aparece justamente em loteamento novo e chácara, que é onde o sistema mais sofre.
**Não dá para escolher entre os dois no escrito:** configure um, rode uma semana de endereços
reais e conte quantos caem na fila de conferência.

Em ambos os adaptadores, o resultado *interpolado* (`RANGE_INTERPOLATED` no Google,
`houseNumberType: interpolated` na HERE) é tratado como **nível de rua**, não como exato. O
provedor estimou o ponto entre os números conhecidos das pontas da quadra; cai perto, e perto
não é o portão. Aceitar isso como exato repetiria o defeito do Nominatim — com uma fatura
junto.

**Limite desta afirmação:** os dois adaptadores foram testados contra respostas gravadas, não
contra as APIs reais — não havia chave disponível quando foram escritos. A leitura das
respostas tem teste (`tests/test_geocoding_pagos.py`), inclusive os casos de cota estourada e
chave inválida, que não podem virar "endereço não encontrado". O que **não** foi exercitado é
a conversa de rede real. Na primeira vez que uma chave for configurada, confira um endereço
conhecido na tela antes de confiar.

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
