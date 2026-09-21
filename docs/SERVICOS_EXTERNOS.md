# Serviços externos

Tudo que o Log Rotas chama fora da própria máquina: para que serve, onde está no código, se
precisa de chave, quanto custa, o que acontece quando cai e como foi conferido.

Situação registrada em **21/09/2026**.

---

## Resumo

| Serviço | Para quê | Chave | Custo | Quem chama | Situação |
|---|---|---|---|---|---|
| [Google Places API (New)](#google-places-api-new) | Busca de endereço com sugestões | Sim | Pago por uso | Servidor | **Funcionando** |
| [Google Geocoding API](#google-geocoding-api) | Dizer se o ponto é o telhado | Sim | Pago por uso | Servidor | Ativada, **recusa por falta de faturamento** |
| [Nominatim](#nominatim-openstreetmap) | Geocodificação gratuita | Não | Grátis, 1 req/s | Servidor | Funcionando |
| [ViaCEP](#viacep) | Endereço a partir do CEP | Não | Grátis | Servidor | Funcionando |
| [AwesomeAPI CEP](#awesomeapi-cep) | Coordenada do trecho do CEP | Não | Grátis | Servidor | Funcionando |
| [OSRM](#osrm) | Distância e tempo pela rua | Não | Grátis | Servidor | Funcionando (servidor de demonstração) |
| [Esri](#esri-ladrilhos-do-mapa) | Desenho do mapa e satélite | Não | Grátis sem conta | Navegador | Funcionando |
| [Google Maps (link)](#google-maps-link-de-navegação) | Navegação do motorista | Não | Grátis | Navegador | Funcionando |
| [Geolocalização do navegador](#geolocalização-do-navegador) | Posição no momento do registro | Não | Grátis | Navegador | Exige HTTPS fora do `localhost` |
| [HERE](#here) | Alternativa ao Google | Sim | Cota gratuita diária | Servidor | **Escrito, nunca testado** |

---

## Chaves e segurança

O repositório é **público**.

1. **Chave só no servidor.** Toda chamada que usa chave sai do backend. O navegador nunca
   recebe uma chave, porque qualquer um lê o JavaScript de uma página.
2. **Chave só no `backend/.env`**, que está no `.gitignore`. O que vai para o Git é o
   `.env.example`, com os nomes das variáveis e nenhum valor.
3. **Nos commits da integração com o Google**, o diff foi varrido à mão atrás do formato das
   chaves do Google (`AIza` + 35 caracteres). **Não há verificação automática** — um
   `git add -A` distraído com a chave num arquivo errado passaria. Um gancho de pre-commit
   que recuse esse padrão resolveria.

No console do Google, a chave deve estar restrita às APIs que usa (Places API (New) e
Geocoding API), com **cota diária** e **alerta de orçamento** configurados. A cota é o que
impede a conta de crescer sozinha; o alerta só avisa.

| Variável | Serviço |
|---|---|
| `GOOGLE_MAPS_API_KEY` | Google Places e Google Geocoding |
| `GEOCODING_PROVIDER` | `nominatim` (padrão), `google` ou `here` — quem faz a geocodificação em lote |
| `GEOCODING_PROVIDER_KEY` | Chave do provedor acima, quando não é o Nominatim |
| `NOMINATIM_BASE_URL`, `NOMINATIM_USER_AGENT` | Nominatim |
| `OSRM_BASE_URL` | OSRM |
| `VITE_MAP_TILE_URL`, `VITE_MAP_ATTRIBUTION` | Troca a base do mapa (frontend) |

---

## Google Places API (New)

**O que faz no sistema:** o campo de endereço "tal qual o Google Maps". A pessoa digita, o
Google sugere endereços que existem, ela escolhe um e o ponto vem junto, com rua, número,
bairro, cidade, UF e CEP.

| | |
|---|---|
| Chamadas | `POST places.googleapis.com/v1/places:autocomplete` (sugestões)<br>`GET places.googleapis.com/v1/places/{id}` (detalhe do lugar escolhido) |
| Código | `backend/app/geocoding/places.py` |
| Endpoints do sistema | `GET /geocodificacao/recursos`, `/sugestoes`, `/lugar/{place_id}` |
| Tela | `frontend/src/components/domain/BuscaEndereco.jsx` |
| Chave | `GOOGLE_MAPS_API_KEY` |

**Por que existe — medido.** Nos mesmos oito endereços reais de Campo Grande, com CEP
conferido:

| | Nominatim | Google Places |
|---|---|---|
| Número certo em Campo Grande | 0 de 8 | **8 de 8** |

O pino do Nominatim ficava de 900 m a 2,3 km do ponto do Google em sete dos oito.

**Decisões:**
- **Token de sessão**, gerado no navegador e repetido em todas as chamadas de uma busca: a
  digitação e a escolha contam como uma cobrança só, em vez de uma por tecla.
- **Viés para Campo Grande** (círculo de 50 km), não restrição: endereço do interior do estado
  continua aparecendo, só mais abaixo na lista.
- **Só os campos usados** no detalhe (`id,formattedAddress,location,types,addressComponents`):
  o Google cobra o detalhe pela faixa dos campos pedidos.
- **Conexão mantida** entre chamadas. Abrindo uma nova a cada tecla, cada sugestão levava ~2 s;
  mantendo, 250 a 700 ms. A primeira depois de o servidor subir ainda leva ~2 s.

**Situação:** funcionando **sem faturamento ativo** no projeto do Google, o que não era
esperado. O Google pode passar a exigir faturamento sem aviso.

**Quando falha:** a tela volta sozinha para a busca por CEP e mostra o motivo (chave recusada,
cota, faturamento, Google fora). O cadastro nunca trava por causa do Google.

---

## Google Geocoding API

**O que faz no sistema:** duas coisas diferentes.

1. **Dizer se o ponto é o telhado.** O Places diz *onde* fica o lugar, mas não se o ponto é o
   prédio ou uma estimativa entre as casas da quadra. A Geocoding responde isso no
   `location_type`. Só `ROOFTOP` dispensa a conferência humana.
2. **Geocodificação em lote pelo Google**, quando `GEOCODING_PROVIDER=google`.

| | |
|---|---|
| Chamada | `GET maps.googleapis.com/maps/api/geocode/json` |
| Código | `backend/app/geocoding/places.py` (`_tipo_do_ponto`) e `backend/app/geocoding/google.py` |
| Chave | `GOOGLE_MAPS_API_KEY` (ou `GEOCODING_PROVIDER_KEY`) |

| `location_type` | Vira | Na prática |
|---|---|---|
| `ROOFTOP` | `EXATO` | Entra em rota sem conferência |
| `RANGE_INTERPOLATED` | `RUA` | Estimado na quadra: pede conferência |
| `GEOMETRIC_CENTER` | `RUA` | Centro da via: pede conferência |
| `APPROXIMATE` | `BAIRRO` | Pede conferência |

**Quem decide que é exato é o servidor.** O navegador manda só o `place_id`. O servidor
procura o lugar no próprio cache — gravado quando o Google respondeu — e só aceita a precisão
se a coordenada recebida for a mesma. Sem isso, qualquer cliente da API gravaria uma coordenada
qualquer como exata.

**Situação:** ativada e liberada na chave, mas responde *"You must enable Billing"*. Até o
faturamento ser ativado, **nenhum ponto vira exato** e todo endereço escolhido pede um clique
de conferência — com o pino já no lugar certo. Depois de uma recusa, o sistema para de
perguntar por 10 minutos e volta a tentar sozinho; não é preciso reiniciar nada ao ativar.

**Quando falha:** mesma coisa que hoje — conferência manual. O log diz a causa (faturamento,
chave sem a API nas restrições, API desativada), porque cada uma se resolve num lugar
diferente do console.

---

## Nominatim (OpenStreetMap)

**O que faz no sistema:** geocodificação gratuita. É o padrão da geocodificação em lote, da
busca na tela de Endereços e da localização automática no caminho por CEP.

| | |
|---|---|
| Chamada | `GET nominatim.openstreetmap.org/search` |
| Código | `backend/app/geocoding/nominatim.py` |
| Chave | Não. **User-Agent identificando a aplicação é obrigatório** |
| Limite | **1 requisição por segundo** e proibição de uso pesado |

**Limite de verdade em Campo Grande:** o OpenStreetMap tem número de porta em cerca de **530
prédios** da cidade (13.864 ruas com nome, 17.404 prédios mapeados). O Nominatim acha a rua,
quase nunca a casa: 0 de 8 nos endereços testados, em consulta livre e estruturada. Por isso
todo ponto que ele devolve é tratado como aproximado e o planejamento o recusa até alguém
conferir. Trocar por Photon, LocationIQ ou MapTiler não resolve: todos leem o mesmo dado.

**Decisões:** um intervalo mínimo de 1,05 s entre chamadas, garantido por uma trava do
processo — com vários workers isso deixa de valer. Resultados vão para o cache no banco
(`geocode_cache`); erro de rede **não** entra no cache, para não virar endereço quebrado
permanente.

**Quando falha:** o registro fica marcado como erro de provedor, não como endereço errado, e
pode ser tentado de novo. Ponto marcado à mão não depende dele.

---

## ViaCEP

**O que faz no sistema:** a partir do CEP, traz logradouro, bairro, cidade e UF dos Correios.

| | |
|---|---|
| Chamada | `GET viacep.com.br/ws/{cep}/json/` |
| Código | `backend/app/geocoding/cep.py` |
| Endpoint do sistema | `GET /geocodificacao/cep/{cep}` |
| Tempo limite | 8 s; cache em memória de até 2.000 CEPs |

**Armadilha tratada:** para CEP inexistente o ViaCEP responde **HTTP 200** com
`{"erro": true}`. Olhar só o código HTTP faria o sistema aceitar um endereço vazio. O sistema
lê o corpo e responde 404.

**Não traz coordenada.** Para isso existe a próxima.

**Quando falha:** a tela pede para digitar o endereço manualmente.

---

## AwesomeAPI CEP

**O que faz no sistema:** coordenada do trecho de rua do CEP, para o mapa abrir na quadra
certa antes de o número ser digitado.

| | |
|---|---|
| Chamada | `GET cep.awesomeapi.com.br/json/{cep}` |
| Código | `backend/app/geocoding/cep.py` (`_coordenada`) |
| Tempo limite | 5 s |

**Por que vale:** o CEP brasileiro é por trecho de rua. Em dez CEPs de Campo Grande conferidos
por geocodificação reversa, nove caem na rua correta. Serve para **posicionar o mapa**; não
serve para ser o ponto da entrega — aponta a quadra, não a porta.

**Descartada no mesmo teste:** a BrasilAPI devolveu **a mesma coordenada para cinco CEPs
diferentes** — um ponto genérico com cara de preciso.

**Não é serviço oficial** e não tem garantia de disponibilidade. **Quando falha:** falha em
silêncio de propósito; o mapa abre na cidade em vez da quadra e o resto funciona igual.

---

## OSRM

**O que faz no sistema:** distância e tempo **pela malha viária** entre as paradas (a matriz
que o otimizador usa) e o traçado da rota que aparece no mapa.

| | |
|---|---|
| Chamadas | `GET /table/v1/driving/...` (matriz)<br>`GET /route/v1/driving/...` (traçado, `overview=full`) |
| Servidor | `router.project-osrm.org` (configurável em `OSRM_BASE_URL`) |
| Código | `backend/app/routing/osrm.py` e `service.py` |
| Tempo limite | 20 s |

**Limite:** é o **servidor público de demonstração**, sem garantia. Para operação de verdade o
caminho é um OSRM próprio com o mapa de MS.

**Quando falha:** cai para estimativa em **linha reta** e **avisa na tela**; o plano registra de
qual fonte veio a matriz, e o mapa desenha a rota tracejada em vez de pela rua.

**Não considera trânsito.** O tempo é o da via livre, com as velocidades do mapa.

---

## Esri (ladrilhos do mapa)

**O que faz no sistema:** o desenho do mapa. Carregado **direto pelo navegador**, sem passar
pelo servidor.

| Camada | Uso |
|---|---|
| `Canvas/World_Light_Gray_Base` + `_Reference` | Mapa claro: base e nomes de rua |
| `Canvas/World_Dark_Gray_Base` + `_Reference` | Mapa escuro |
| `World_Imagery` | Satélite, para conferir o portão |
| `Reference/World_Transportation` | Nomes de rua por cima do satélite |

| | |
|---|---|
| Código | `frontend/src/components/map/MapPanel.jsx` |
| Chave | Não |

**Conferido:** imagem de satélite real até o **zoom 19**, no centro e num bairro afastado. No
zoom 20 a Esri devolve um ladrilho chapado de 2.521 bytes; por isso o limite é 19. A camada
`World_Boundaries_and_Places` foi testada e volta vazia nesses zooms, então não é usada.

**Termos:** uso comercial pede conta ArcGIS. Para trocar de base sem mexer no código, defina
`VITE_MAP_TILE_URL` e `VITE_MAP_ATTRIBUTION`.

**Lição que ficou:** a base anterior era da CARTO, que passou a exigir chave e começou a
devolver **HTTP 200 com um PNG válido** carimbado "API KEY REQUIRED". Nenhuma verificação por
código de resposta pega isso. Troca de provedor de mapa é conferida **olhando a tela**.

---

## Google Maps (link de navegação)

**O que faz no sistema:** o botão **Navegar** do app do motorista abre o Google Maps (ou o app
instalado) com o destino na próxima parada, para a navegação curva a curva.

| | |
|---|---|
| Endereço | `https://www.google.com/maps/dir/?api=1&destination={lat},{lon}` |
| Código | `frontend/src/pages/driver/DriverRoute.jsx` |
| Chave / custo | Não / grátis — é um link, não uma chamada de API |

O Log Rotas não faz navegação curva a curva; delega a quem faz, com trânsito.

---

## Geolocalização do navegador

**O que faz no sistema:** quando o motorista registra "cheguei", "entregue" ou "não
entregue", o app pega a posição do aparelho **naquele momento** e grava junto com o evento.

| | |
|---|---|
| API | `navigator.geolocation.getCurrentPosition` |
| Código | `frontend/src/pages/driver/DriverRoute.jsx` |
| Parâmetros | tempo limite 5 s, posição aceita com até 30 s de idade |

**Não é rastreamento contínuo.** O sistema não sabe onde o caminhão está entre um registro e
outro.

**Nunca trava o motorista:** sem sinal, sem permissão ou sem HTTPS, o registro é gravado sem
coordenada. **O navegador só libera a localização em HTTPS** (ou em `localhost`) — em produção,
sem certificado, nenhum evento terá posição.

---

## HERE

**O que faz no sistema:** nada, por enquanto. É uma alternativa ao Google para a
geocodificação em lote, ativada com `GEOCODING_PROVIDER=here` e `GEOCODING_PROVIDER_KEY`.

| | |
|---|---|
| Chamada | `GET geocode.search.hereapi.com/v1/geocode` |
| Código | `backend/app/geocoding/here.py` |

**Nunca foi testado contra a API real** — não havia chave. A leitura das respostas tem testes
com respostas gravadas (`backend/tests/test_geocoding_pagos.py`); a conversa de rede, não.
Antes de confiar, confira um endereço conhecido na tela.

---

## O que acontece quando cada um cai

| Fora do ar | O sistema |
|---|---|
| Google Places | Volta para a busca por CEP, com o motivo na tela |
| Google Geocoding | Nenhum ponto vira exato; todo endereço pede um clique de conferência |
| Nominatim | Marca erro de provedor (não "endereço errado") e permite tentar de novo |
| ViaCEP | Pede o endereço digitado por extenso |
| AwesomeAPI | Mapa abre na cidade em vez da quadra |
| OSRM | Distância em linha reta, **com aviso na tela** e a fonte registrada no plano |
| Esri | Mapa sem desenho; cadastro, planejamento e execução continuam |
| Geolocalização | Evento gravado sem coordenada |

Nenhum deles impede de cadastrar, planejar ou executar uma rota. O que muda é a precisão — e
o sistema sempre diz quando a precisão caiu.

---

## Usados só para medir, não pelo sistema

| Serviço | Para quê |
|---|---|
| Overpass API (OpenStreetMap) | Contar ruas, prédios e números de porta de Campo Grande no mapa aberto |

## Não são serviços externos

**OR-Tools** (otimização das rotas) e **Leaflet** (o componente de mapa) são bibliotecas que
rodam na própria máquina. Nenhuma das duas faz chamada para fora — quem busca os ladrilhos
que o Leaflet mostra é a Esri, acima.
