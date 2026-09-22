# API

Base: `/api/v1` · Documentação interativa: <http://localhost:8000/docs>

Autenticação por `Authorization: Bearer <access_token>`, exceto onde indicado.

---

## Formato de erro

Toda resposta de erro de domínio tem o mesmo formato:

```json
{
  "erro": "conflito",
  "mensagem": "O e-mail carlos@britto.com.br ja esta cadastrado.",
  "detalhes": {}
}
```

| `erro` | HTTP | Quando |
|---|---|---|
| `validacao` | 422 | Dado inválido |
| `nao_autenticado` | 401 | Sem token, token inválido ou sessão encerrada |
| `sem_permissao` | 403 | Papel sem acesso à operação |
| `nao_encontrado` | 404 | Registro inexistente |
| `conflito` | 409 | Unicidade ou estado incompatível |
| `transicao_invalida` | 409 | Mudança de status proibida (fases futuras) |
| `tentativas_demais` | 429 | Login bloqueado por tentativas; vem com `Retry-After` e `detalhes.tente_em_segundos` |
| `banco_indisponivel` | 503 | Falha de banco |

Erros de validação do Pydantic seguem o formato padrão do FastAPI (`detail`), e o frontend
trata os dois.

---

## Infraestrutura

### `GET /health`

Pública. Verifica a API e a conexão com o banco.

```json
{ "status": "ok", "banco": "ok" }
```

---

## Primeiro acesso

Rotas públicas, disponíveis **apenas enquanto o sistema não tem nenhum usuário**.

### `GET /api/v1/setup/status`

```json
{ "needs_setup": true }
```

O frontend consulta antes de mostrar o login: com o sistema vazio, leva direto ao primeiro
acesso em vez de apresentar um login que ninguém conseguiria usar.

### `POST /api/v1/setup`

Cria a empresa e o administrador inicial **na mesma transação**, e já devolve a sessão
autenticada.

```json
{
  "company_name": "Britto Moveis e Corrimao",
  "admin_name": "Bruno",
  "admin_email": "bruno@britto.com.br",
  "admin_password": "SenhaForte123"
}
```

**201** → `{ access_token, refresh_token, token_type, expires_in, user }`
**409** → o sistema já foi configurado. A rota se fecha para sempre.

---

## Autenticação

### `POST /api/v1/auth/login`

Pública.

```json
{ "email": "bruno@britto.com.br", "password": "pão de queijo quente 7" }
```

**200** → `{ access_token, refresh_token, token_type, expires_in, user, senha_fraca }`
**401** → `"E-mail ou senha incorretos."` — mesma mensagem e mesmo tempo de resposta para
senha errada, e-mail inexistente e usuário desativado.
**429** → bloqueado por tentativas (5 erros na conta ou 20 no IP em 15 min, por padrão). Durante
o bloqueio nem a senha certa entra. Ver [SEGURANCA.md](SEGURANCA.md).

`senha_fraca: true` quando a senha usada não passaria na política de hoje: o login funciona, e a
tela pede a troca.

O e-mail não diferencia maiúsculas de minúsculas.

### `POST /api/v1/auth/refresh`

Pública (autentica pelo próprio refresh token).

```json
{ "refresh_token": "..." }
```

**200** → novo par de tokens. Um access token **não** é aceito aqui, e um refresh token **não**
abre rota protegida.

### `GET /api/v1/auth/me`

Dados do usuário autenticado.

### `POST /api/v1/auth/senha`

Troca a própria senha.

```json
{ "current_password": "a senha de hoje", "new_password": "girafa roxa na janela 5" }
```

**200** → um par de tokens novo. A troca encerra todas as sessões anteriores; por isso quem
trocou recebe tokens novos e não é deslogado do próprio navegador.
**401** → senha atual incorreta.
**422** → a senha nova não passa na política. Todos os motivos vêm de uma vez, em
`detalhes.problemas` (ex.: `["Tem menos de 10 caracteres.", "É uma senha muito usada ..."]`).

A mesma política — e o mesmo 422 — vale na criação de usuário, na redefinição pelo administrador
e no primeiro acesso.

---

## Usuários — somente `ADMIN`

### `GET /api/v1/usuarios`

Parâmetros opcionais: `role` (`ADMIN` | `MOTORISTA`), `active` (bool), `search` (nome ou
e-mail).

### `POST /api/v1/usuarios`

```json
{
  "name": "Carlos Entregador",
  "email": "carlos@britto.com.br",
  "password": "SenhaProvisoria1",
  "role": "MOTORISTA",
  "active": true
}
```

**201** → usuário criado · **409** → e-mail já cadastrado.

Senha mínima: 10 caracteres.

### `GET /api/v1/usuarios/{id}`

### `PATCH /api/v1/usuarios/{id}`

Aceita `name`, `role`, `active` — todos opcionais.

**422** se a alteração deixaria o sistema sem nenhum administrador ativo.

Desativar um usuário **encerra as sessões abertas dele imediatamente**.

### `POST /api/v1/usuarios/{id}/senha`

Redefinição pelo administrador, sem exigir a senha atual. Usado quando o motorista esquece a
senha.

```json
{ "new_password": "lanterna de cobre velha 8" }
```

Encerra as sessões do usuário. A senha nova não é devolvida em lugar nenhum — o administrador
a informa pessoalmente.

---

## Configurações — somente `ADMIN`

### `GET /api/v1/configuracoes`

**404** enquanto o primeiro acesso não tiver sido concluído.

### `PATCH /api/v1/configuracoes`

Todos os campos opcionais: `company_name`, `document`, `phone`, `email`, `timezone`,
`default_stop_service_minutes` (1 a 1440).

---

## Cadastros — somente `ADMIN`

Os quatro cadastros expõem a mesma interface:

| Método | Caminho | |
|---|---|---|
| `GET` | `/api/v1/{recurso}` | Lista. Filtros: `active` (bool), `search` (texto) |
| `POST` | `/api/v1/{recurso}` | Cria |
| `GET` | `/api/v1/{recurso}/{id}` | Detalhe |
| `PATCH` | `/api/v1/{recurso}/{id}` | Altera; só os campos enviados |

Recursos: `bases`, `veiculos`, `motoristas`, `clientes`.

Nenhum registro é apagado — `active: false` desativa. O histórico de rotas vai depender
desses registros, e apagar um veículo levaria junto a explicação de por que uma rota antiga
foi montada daquele jeito.

### Bases

Campos: `name`, `address`, `phone`, `latitude`, `longitude`, `is_default`, `active`, `notes`.

**Regras:**
- a primeira base cadastrada vira a padrão automaticamente;
- marcar uma como padrão desmarca a anterior — duas padrão deixariam o planejador sem critério;
- desativar uma base limpa o `is_default`, porque ela seria oferecida por default e falharia.

### Veículos

Campos: `name`, `plate`, `model`, `capacity_weight_kg`, `capacity_volume_m3`,
`capacity_length_m`, `max_stops`, `crew_size`, `active`, `notes`.

**Regras:**
- a placa é normalizada antes de gravar (sem máscara, em maiúsculas) e é única. Enviar
  `abc-1234` quando já existe `ABC1234` devolve **409**;
- formatos aceitos: `ABC1234` (antigo) e `ABC1D23` (Mercosul). Qualquer outro devolve **422**;
- **todas as capacidades são opcionais.** Ainda não se sabe qual limita a operação da Britto,
  e exigir qualquer uma obrigaria a inventar número. Cada uma preenchida poderá virar
  restrição do otimizador; as vazias são ignoradas.

### Motoristas

Campos: `name`, `user_id`, `phone`, `document`, `license_number`, `license_expires_at`,
`active`, `notes`.

**Regras:**
- `user_id` é opcional: motorista terceirizado, ou ainda sem acesso criado, existe
  normalmente e já pode receber rota;
- vincular um usuário com perfil `ADMIN` devolve **422** — ele passaria a aparecer como quem
  leva carga;
- o mesmo usuário não pode estar vinculado a dois motoristas (**409**);
- `user_id` inexistente devolve **404**.

### Clientes

Campos: `name`, `phone`, `email`, `document`, `address`, `latitude`, `longitude`, `active`,
`notes`.

**Regras:**
- `document` (CPF/CNPJ) é único quando informado, e a comparação ignora máscara. Vários
  clientes podem ficar sem documento;
- telefone e documento são guardados **apenas com dígitos** — guardar `(67) 99999-0000` e
  `67999990000` como valores distintos tornaria qualquer busca pouco confiável.

### Endereço e coordenada

Vale para bases e clientes, e valerá para entregas.

| Situação | O que acontece |
|---|---|
| Enviou `latitude` + `longitude` | `geocode_status` vira **`MANUAL`**, que a geocodificação automática nunca sobrescreve |
| Alterou `address` sem coordenada | A coordenada antiga é **descartada** e o status volta para `PENDENTE` |
| Alterou qualquer outro campo | Coordenada e status ficam como estão |
| Enviou só uma das duas coordenadas | **422** — uma sem a outra não localiza nada |

A segunda regra é a que evita rota calculada para o endereço errado: sem ela, editar
"Rua A, 100" para "Rua B, 500" manteria o pino na Rua A sem nenhum aviso.

Status possíveis: `PENDENTE`, `OK`, `AMBIGUO`, `FALHOU`, `MANUAL`.

---

## Entregas — somente `ADMIN`

| Método | Caminho | |
|---|---|---|
| `GET` | `/api/v1/entregas` | Filtros: `data`, `data_de`, `data_ate`, `status` (repetível), `priority`, `customer_id`, `sem_coordenada`, `search` |
| `GET` | `/api/v1/entregas/resumo` | Contagem por status |
| `POST` | `/api/v1/entregas` | Cria |
| `GET` | `/api/v1/entregas/{id}` | Detalhe |
| `GET` | `/api/v1/entregas/{id}/historico` | Registro append-only de cada mudança |
| `PATCH` | `/api/v1/entregas/{id}` | Altera |
| `POST` | `/api/v1/entregas/{id}/status` | Muda o status |

**Regras:**
- endereço **ou** cliente é obrigatório — entrega sem destino não tem para onde ir;
- selecionar cliente **copia** endereço e coordenada para a entrega. O cliente pode mudar de
  endereço depois, e a entrega precisa guardar para onde ela foi de fato;
- peso, volume, comprimento, equipe e tempo de serviço são opcionais;
- janela de horário invertida responde 422 no cadastro — deixada passar, só apareceria na
  otimização como "sem solução";
- entrega em rota **trava** os campos que afetam o planejamento (peso, endereço, data,
  janela). Responde 422 listando os campos bloqueados;
- `NAO_ENTREGUE` exige motivo, e o motivo `OUTRO` exige descrição.

Transição impossível responde **409** dizendo quais status eram possíveis.

---

## Geocodificação — somente `ADMIN`

| Método | Caminho | |
|---|---|---|
| `GET` | `/api/v1/geocodificacao/pendentes` | Fila de revisão |
| `GET` | `/api/v1/geocodificacao/cep/{cep}` | Endereço dos Correios |
| `GET` | `/api/v1/geocodificacao/buscar?endereco=...` | Candidatos para o mapa |
| `GET` | `/api/v1/geocodificacao/recursos` | O que está ligado (`autocomplete`) |
| `GET` | `/api/v1/geocodificacao/sugestoes?texto=...&sessao=...` | Sugestões do Google |
| `GET` | `/api/v1/geocodificacao/lugar/{place_id}?sessao=...` | Detalhe do lugar escolhido |
| `POST` | `/api/v1/geocodificacao/testar?endereco=...` | Consulta sem gravar |
| `POST` | `/api/v1/geocodificacao/lote` | Processa uma fila |
| `POST` | `/api/v1/geocodificacao/{tipo}/{id}` | Geocodifica um registro |
| `PUT` | `/api/v1/geocodificacao/{tipo}/{id}/coordenada` | Grava o pino manual |

`tipo` é `entrega`, `cliente` ou `base`.

> **A ordem desta tabela é a ordem do código, e isso importa.** `/{tipo}/{id}` casa com
> qualquer coisa de dois segmentos, inclusive `/cep/79002000`. Registrar a rota genérica
> antes das fixas devolve **405** num caminho que existe. Há teste de regressão para as duas.

### Busca do Google: `/sugestoes` e `/lugar/{place_id}`

`sessao` é um token gerado no navegador (UUID) e repetido em todas as chamadas de uma mesma
busca: o Google cobra a digitação e a escolha como uma sessão só. A chamada ao Google sai do
servidor; a chave nunca chega ao navegador.

`/lugar` devolve logradouro, número, bairro, cidade, UF, CEP, coordenada, `precision` e
`tipo_ponto` (`ROOFTOP`, `RANGE_INTERPOLATED`... ou `null` quando a Geocoding API não
respondeu). E grava o resultado em cache — é contra ele que o servidor confere, ao salvar,
se a coordenada recebida com `google_place_id` é a que o Google devolveu.

Sem `GOOGLE_MAPS_API_KEY`, `/sugestoes` e `/lugar` respondem **503** com a instrução.

### Gravar a origem do ponto

Entregas, clientes e bases aceitam, junto com `latitude`/`longitude`:

| Campo | Efeito |
|---|---|
| `ponto_confirmado: true` | Uma pessoa marcou ou conferiu o ponto → `MANUAL` |
| `google_place_id` | O servidor procura o lugar no cache; se a coordenada for a mesma, grava a precisão que o Google provou |
| nenhum dos dois | Coordenada gravada como aproximada (`RUA`) — o planejamento recusa |

### `GET /cep/{cep}`

Consulta o ViaCEP e devolve logradouro, bairro, cidade e UF já normalizados. Aceita o CEP com
ou sem máscara.

```json
{
  "cep": "79002000",
  "cep_formatado": "79002-000",
  "logradouro": "Avenida Calógeras",
  "bairro": "Centro",
  "cidade": "Campo Grande",
  "uf": "MS",
  "endereco_montado": "Avenida Calógeras, Centro, Campo Grande - MS, 79002-000"
}
```

Com `?numero=1500`, `endereco_montado` já vem com o número na posição certa — a interface não
precisa saber montar endereço brasileiro.

CEP inexistente devolve **404**. A pegadinha está do lado do provedor: o ViaCEP responde
`200` com `{"erro": true}`, um status de sucesso carregando uma falha — quem olhasse só o
código HTTP gravaria um endereço vazio.

O CEP **não traz coordenada**: os Correios dão o logradouro, não o número. A posição vem do
`/buscar` com o endereço já montado.

### `GET /buscar`

Geocodifica sem gravar nada e devolve **todos** os candidatos, para a interface mostrar o
primeiro no mapa e deixar a lista à vista quando houver mais de um.

```json
{
  "consulta": "Avenida Calógeras, 1500, Centro, Campo Grande - MS",
  "candidatos": [
    {
      "latitude": -20.4697,
      "longitude": -54.6201,
      "display_name": "Avenida Calógeras, Centro, Campo Grande - MS",
      "precision": "RUA"
    }
  ]
}
```

`precision` é `EXATO`, `RUA`, `BAIRRO` ou `CIDADE`. `RUA` significa que o pino está na via
certa e pode estar algumas dezenas de metros do número — a tela avisa em vez de fingir
precisão. Gravar é um passo separado, por `PUT .../coordenada`.

**Quatro desfechos, e a distinção importa:**

| Status | Significa | Coordenada |
|---|---|---|
| `OK` | Resposta confiável | Gravada |
| `AMBIGUO` | Vários endereços possíveis | **Não gravada** — quem decide é o humano |
| `FALHOU` | O provedor não achou | Não gravada |
| `ERRO_PROVEDOR` | Rede, limite, indisponibilidade | Não gravada, e **não entra no cache** |

Endereço não encontrado exige corrigir o endereço; erro de provedor exige tentar de novo. Um
pino `MANUAL` nunca é sobrescrito sem `forcar=true`.

O lote **demora**: o Nominatim permite uma consulta por segundo.

---

## Planejamento — somente `ADMIN`

| Método | Caminho | |
|---|---|---|
| `GET` | `/api/v1/planejamento` | Lista |
| `POST` | `/api/v1/planejamento/calcular` | Calcula e devolve **rascunho** |
| `GET` | `/api/v1/planejamento/{id}` | Detalhe com rotas e paradas |
| `POST` | `/api/v1/planejamento/{id}/confirmar` | Põe em operação |
| `POST` | `/api/v1/planejamento/{id}/descartar` | Joga fora |

### `POST /calcular`

```json
{
  "date": "2026-09-20",
  "base_id": 1,
  "delivery_ids": [1, 2, 3],
  "vehicle_ids": [1, 2],
  "driver_ids": [1, 2],
  "inicio_turno": "08:00",
  "limite_tempo_s": 15
}
```

**Calcular não muda a operação.** As entregas continuam `PENDENTE`, nenhuma rota fica
disponível para motorista.

Por dentro, em ordem: agrupa entregas por lugar (uma parada resolve várias), monta a matriz de
distâncias e resolve com OR-Tools minimizando **tempo**.

Recusas, todas com o motivo:

| HTTP | Quando |
|---|---|
| 422 | Entregas sem coordenada, **com a lista** |
| 422 | Base sem coordenada, veículo ou motorista inativo |
| 409 | Entregas que não estão mais pendentes |
| 409 | O solver não encontrou solução, com as estatísticas |

A resposta traz `matrix_source`, `distancias_estimadas`, `avisos`, `solver_status`,
`solver_time_ms` e `unassigned` — o que não coube, com o motivo.

### `POST /{id}/confirmar`

Rotas viram `PLANEJADA`, entregas viram `PLANEJADA`. **Toda rota precisa de motorista** — sem
isso responde 422. Um plano confirmado não volta atrás.

---

## Motorista — somente `MOTORISTA`

| Método | Caminho | |
|---|---|---|
| `GET` | `/api/v1/motorista/rotas` | Rotas do dia |
| `GET` | `/api/v1/motorista/rotas/{id}` | Detalhe com progresso |
| `POST` | `/api/v1/motorista/rotas/{id}/iniciar` | Sai da base |
| `POST` | `/api/v1/motorista/paradas/{id}/cheguei` | Registra chegada |
| `POST` | `/api/v1/motorista/entregas/{id}/entregue` | Conclui **uma** entrega |
| `POST` | `/api/v1/motorista/entregas/{id}/nao-entregue` | Registra insucesso |
| `POST` | `/api/v1/motorista/rotas/{id}/finalizar` | Encerra o dia |

**Isolamento:** rota de outro motorista responde **404**, não 403 — dizer "existe, mas não é
sua" confirmaria a existência de rotas alheias. Planejamento em rascunho não aparece.

**Coordenada é opcional** em todo registro: o navegador só libera geolocalização em contexto
seguro, e nem sempre há sinal.

**Finalizar não dá por entregue o que ficou sem registro.** Essas entregas viram
`NAO_ENTREGUE`, com a observação de que a rota foi encerrada sem registro, e voltam para o
planejamento.

---

## Painel — somente `ADMIN`

### `GET /api/v1/painel?data=...`

Uma chamada devolve indicadores, rotas ativas com geometria e os pontos do mapa. O painel
atualiza por polling, e quatro requisições por ciclo multiplicariam a carga sem ganho.

`CHEGOU` conta como "em rota": para quem olha o painel, o motorista parado na porta do cliente
ainda está na rua. Só rotas confirmadas entram no total — rascunho é cenário, não compromisso.

---

## Segurança — somente `ADMIN`

| Método | Caminho | |
|---|---|---|
| `GET` | `/api/v1/seguranca/politica` | Regras em vigor, lidas da configuração |
| `GET` | `/api/v1/seguranca/bloqueios` | Contas bloqueadas agora, com nome, falhas e `ate` |
| `POST` | `/api/v1/seguranca/bloqueios/desbloquear` | `{ "email": "..." }` — libera antes do tempo; fica registrado quem liberou |
| `GET` | `/api/v1/seguranca/eventos?limite=100` | Eventos recentes (`tipo`, `quem`, `sobre`, `ip`, `detalhe`, `quando`) |

Desbloquear devolve a lista de bloqueios atualizada.

---

## Manutenção — somente `ADMIN`

### `GET /api/v1/manutencao`

```json
{ "hora_agendada": 3, "retencao_posicoes_dias": 90, "retencao_tentativas_login_dias": 180,
  "retencao_eventos_seguranca_dias": 730, "retencao_cache_falhas_dias": 30,
  "ultimas": [ { "id": 7, "origem": "AGENDADA", "iniciada_em": "...", "terminada_em": "...",
                 "resultado": { "posicoes": 3512, "tentativas_login": 0, "eventos_seguranca": 0,
                                "cache_falhas": 2, "cache_google": 41 },
                 "erro": null } ] }
```

`hora_agendada` é nulo quando a limpeza automática está desligada (`LIMPEZA_HORA=-1`).

### `POST /api/v1/manutencao/limpar`

Roda a limpeza agora, sem esperar o horário. Devolve o mesmo corpo do `GET`, com a execução nova
em primeiro. **409** se outra limpeza estiver em andamento. Pela linha de comando:
`python -m app.tarefas limpar`.

---

## Ainda não implementado

| Recurso | Observação |
|---|---|
| Retorno à base para recarregar | O modelo comporta (`stop_type`, `trip_number`); falta no solver |
| Relatórios e indicadores históricos | O `delivery_events` já guarda tudo que eles precisam |
| Importação CSV de entregas | — |
| Foto, assinatura e código de barras | — |
| GPS contínuo do motorista | Exige HTTPS e troca de polling por SSE |


---

## Rastreamento ao vivo

| Método | Caminho | Quem | |
|---|---|---|---|
| `POST` | `/api/v1/motorista/rotas/{id}/posicoes` | `MOTORISTA` | GPS em lote |
| `GET` | `/api/v1/motorista/rotas/{id}/navegacao?latitude=&longitude=` | `MOTORISTA` | Rota até a próxima parada |
| `GET` | `/api/v1/painel/ao-vivo` | `ADMIN` | Caminhões em rota agora |

### `POST /posicoes`

```json
{ "posicoes": [ { "latitude": -20.4650, "longitude": -54.6150,
                  "registrada_em": "2026-09-21T17:30:05.120Z",
                  "precisao_m": 8, "velocidade_mps": 11.2, "direcao_graus": 90 } ] }
```

`registrada_em` é a hora **do aparelho**, quando o GPS mediu — o celular pode mandar um trecho
inteiro de uma vez depois de ficar sem sinal. Resposta:

```json
{ "aceitas": 1, "repetidas": 0, "descartadas": 0, "motivos": {} }
```

- **Descartadas**, com o motivo: GPS pior que 150 m, relógio adiantado mais de 2 min, anterior
  ao início da rota, rota fora de execução. Um ponto ruim não derruba o lote.
- **Repetidas**: a mesma medição reenviada como sinal de vida. Não vira linha nova; renova a
  hora de contato. É o que separa "parado" de "sem sinal".

### `GET /navegacao`

Trajeto da posição informada até a próxima parada aberta (a base, quando as entregas acabam),
com `geometria` (polyline), `manobras` (instrução em português, distância, ponto), `distancia_m`,
`duracao_s`, `chegada_prevista`, `com_transito`, `estimada` e `aviso`.

`latitude_chegada`/`longitude_chegada` **não é o pino**: é o ponto, na rua do endereço, mais
próximo dele. Exige a rota iniciada (**422** caso contrário).

### `GET /painel/ao-vivo`

Por rota em andamento: `situacao` (`EM_MOVIMENTO`, `PARADO`, `NA_PARADA`, `SEM_SINAL`,
`SEM_POSICAO`), `posicao`, `idade_s` (idade da medição), `rastro` (últimos 30 min), `proxima` e
`previsao` — cada parada com `chegada_prevista`, `chegada_planejada`, `atraso_s` e `espera_s`.

`previsao.fonte` diz de onde veio o tempo: `OSRM+TRANSITO`, `OSRM` (rua livre), `HAVERSINE`
(linha reta) ou `PLANEJADO` (nenhuma posição ainda — são os horários do plano, não previsão).
A previsão é recalculada no máximo a cada 45 s por rota, e imediatamente quando chega a
primeira posição.
