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

## Ainda não implementado

| Recurso | Fase |
|---|---|
| `/clientes`, `/motoristas`, `/veiculos`, `/bases` | 3 |
| `/entregas` | 3 |
| `/geocodificacao` | 4 |
| `/planejamento` (calcular, revisar, confirmar) | 7 |
| `/rotas` | 7 |
| `/painel` | 8 |
| `/motorista` (rota do dia, chegada, entrega, ocorrência) | 9 |
