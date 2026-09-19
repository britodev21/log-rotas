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
{ "email": "bruno@britto.com.br", "password": "SenhaForte123" }
```

**200** → `{ access_token, refresh_token, token_type, expires_in, user }`
**401** → `"E-mail ou senha incorretos."` — mesma mensagem e mesmo tempo de resposta para
senha errada, e-mail inexistente e usuário desativado.

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
{ "current_password": "SenhaAtual1", "new_password": "NovaSenha456" }
```

**200** → um par de tokens novo. A troca encerra todas as sessões anteriores; por isso quem
trocou recebe tokens novos e não é deslogado do próprio navegador.
**401** → senha atual incorreta.

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
{ "new_password": "OutraSenha789" }
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

## Ainda não implementado

| Recurso | Fase |
|---|---|
| `/entregas` | 3 |
| `/geocodificacao` | 4 |
| `/planejamento` (calcular, revisar, confirmar) | 7 |
| `/rotas` | 7 |
| `/painel` | 8 |
| `/motorista` (rota do dia, chegada, entrega, ocorrência) | 9 |
