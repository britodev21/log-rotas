# Arquitetura

Decisões técnicas do Log Rotas e a razão de cada uma. Documento vivo: cada fase acrescenta a
sua parte.

---

## 1. Forma geral

**Monólito modular em camadas, com portas e adaptadores nos pontos que precisam ser
trocáveis.**

Microsserviços foram descartados: o produto tem um único fluxo transacional (planejar →
executar) e a separação por processo custaria meses sem resolver problema nenhum. O que
precisa ser desacoplado aqui não são processos — são fornecedores externos e algoritmos, e
isso se resolve com interface, não com rede.

```
API (FastAPI routers)   →  HTTP, autenticação, autorização, códigos de status
  ↓
SERVICES                →  regra de negócio, transições de estado, transação
  ↓
REPOSITORIES            →  a única camada que monta SQL
  ↓
MODELS (SQLAlchemy)     →  mapeamento das tabelas, sem regra
```

Regra de dependência: sempre para baixo. Um repositório nunca importa um service; um model
nunca importa nada de `api/`.

### Módulos plugáveis (fases futuras)

| Módulo | Porta | Adaptador inicial | Trocável por |
|---|---|---|---|
| `geocoding/` | `GeocodingProvider` | Nominatim | Google, LocationIQ, Photon, ViaCEP |
| `routing/` | `MatrixProvider` | OSRM | OSRM próprio, ORS, Google Matrix |
| `optimization/` | `OptimizationEngine` | OR-Tools | outro solver |

O módulo `optimization/` **não importará SQLAlchemy nem FastAPI**. Ele recebe dataclasses
puras e devolve dataclasses puras. É a única forma de testá-lo isolado e de trocá-lo depois.

---

## 2. Decisões e justificativas

### 2.1 Aplicação de empresa única, não SaaS

O Log Rotas é a aplicação da Britto Móveis e Corrimão. Multi-tenancy foi retirada do desenho.

Custo evitado: `company_id` em todas as tabelas, índices correspondentes, chaves estrangeiras
compostas, contexto de tenant em toda dependência HTTP e em toda assinatura de repositório —
complexidade em todos os arquivos, todos os dias, servindo a zero clientes.

Custo de reverter, se um dia virar produto: migration mecânica (adicionar coluna, preencher
com 1, tornar obrigatória, criar índices, ajustar repositórios). Um a dois dias.

No lugar da tabela `companies`, uma tabela `company_settings` de **linha única**, garantida
por `CHECK (id = 1)`. Não é multi-tenancy — é configuração editável pelo administrador.

### 2.2 SQLAlchemy 2.0, estilo Core, síncrono

As queries são escritas com `select()` — API Core, SQL transparente, sem lazy loading
escondido. Os modelos declarativos preservam chaves estrangeiras e constraints.

Síncrono, com endpoints `def`, que o FastAPI executa em threadpool. Async ORM adicionaria uma
classe inteira de armadilhas (sessão vazando entre tasks, greenlets) para ganhar throughput
que esta operação nunca vai precisar. Decisão reversível.

### 2.3 Chaves primárias `BIGINT IDENTITY`

`entrega #1047` é algo que a equipe vai falar no telefone e digitar num campo de busca. UUID
faria sentido contra enumeração de recursos num SaaS público; num sistema interno e
autenticado, é só atrito.

### 2.4 Enums como `VARCHAR` + `CHECK`, não `ENUM` nativo

Alterar um `ENUM` do Postgres em migration é doloroso, e esta lista vai crescer
(`RETORNANDO_BASE`, `RECARREGANDO`). `VARCHAR` + `CHECK` dá a mesma integridade com migration
trivial.

Os valores são ASCII e maiúsculos: `NAO_ENTREGUE`, nunca `NÃO_ENTREGUE`. Acento em
identificador quebra URL, CSV e integração. A tradução para "Não entregue" acontece na
interface.

### 2.5 Senhas com Argon2id

`argon2-cffi` usado diretamente, não via passlib — passlib está sem manutenção ativa e quebra
com versões recentes do bcrypt. O hash é reavaliado a cada login (`check_needs_rehash`) e
atualizado quando os parâmetros mudam; é o único momento em que a senha em claro existe.

### 2.6 JWT com revogação por `token_version`

Token de acesso de 60 minutos e token de renovação de 7 dias, ambos assinados com HS256.

`users.token_version` é um inteiro incluído no payload. Incrementá-lo invalida na hora todos
os tokens já emitidos para aquele usuário. É o que faz troca de senha, desativação de conta e
redefinição pelo administrador derrubarem as sessões abertas imediatamente, em vez de esperar
o token expirar.

O cliente HTTP do frontend renova a sessão automaticamente em caso de 401, com uma única
renovação concorrente por vez.

### 2.7 Login que não revela quais e-mails existem

Senha errada, e-mail inexistente e usuário desativado devolvem a mesma mensagem. Além disso,
quando o e-mail não existe o serviço calcula um hash descartável, para que a resposta demore o
mesmo tanto — sem isso, a diferença de tempo entregaria a lista de e-mails cadastrados.

### 2.8 Excepções de domínio traduzidas num lugar só

Services e repositórios levantam `NotFoundError`, `ConflictError`, `ValidationError`,
`AuthenticationError`, `PermissionDeniedError` — nenhum deles conhece código HTTP. A tradução
acontece uma única vez, nos handlers registrados em `main.py`, e toda resposta de erro tem o
mesmo formato:

```json
{ "erro": "conflito", "mensagem": "...", "detalhes": {} }
```

`IntegrityError` do banco vira 409 com mensagem genérica: a mensagem original do Postgres
revelaria nomes de tabela e coluna.

### 2.9 Autorização declarada, nunca improvisada

Nenhum endpoint decodifica token ou confere papel por conta própria. Todos declaram
`CurrentUser`, `AdminUser` ou `DriverUser`, construídos em `api/deps.py`. Assim não existe rota
protegida por engano — ou a dependência está lá, ou a rota é pública de propósito.

### 2.10 Travas contra estado impossível

Duas já implementadas, ambas no `UserService`:

- o último administrador ativo não pode ser rebaixado nem desativado — sem isso, um clique
  tranca a empresa para fora do próprio sistema;
- desativar um usuário incrementa `token_version`, encerrando as sessões abertas dele.

### 2.11 Versionamento da API desde o primeiro dia

Todas as rotas vivem sob `/api/v1`. Quando existir aplicativo instalado no celular do
motorista, quebrar contrato sem versionar deixaria aparelhos antigos sem funcionar.

---

## 3. Frontend

### 3.1 CSS puro com tokens

`styles/tokens.css` é a fonte única de cor, espaçamento e tipografia. Nenhum componente
escreve valor cru. Cada componente tem o seu `.css` ao lado do `.jsx`.

As cores de estado (`--cor-sucesso`, `--cor-atencao`, `--cor-erro`) são as mesmas que serão
usadas pelos status de entrega, para que verde signifique "entregue" na lista, no mapa e na
tela do motorista.

### 3.2 Duas cascas, não uma encolhida

`AdminLayout` é desenhado para desktop, com o menu virando gaveta no celular.
`DriverLayout` é outra coisa: sem menu lateral, sem navegação profunda, área de toque mínima
de 48px, respeitando o recorte de tela do aparelho. O motorista opera de pé, com pressa.

O campo de formulário usa fonte de 16px no celular porque, abaixo disso, o iOS dá zoom
sozinho ao focar o campo e desalinha a tela inteira.

### 3.3 Nenhuma regra de negócio no componente

Componente React não chama `axios` diretamente: tudo passa por `api/client.js`, onde ficam
token, renovação de sessão e tradução de erro. A tela cuida de tela.

### 3.4 A interface não inventa dado

Itens de menu ainda não implementados aparecem desabilitados, com a fase em que entram. O
painel mostra o andamento da implantação em vez de indicadores. A tela do motorista diz que
não há rota atribuída. Ver [LIMITACOES.md](LIMITACOES.md).

---

## 4. Testes

Rodam contra PostgreSQL de verdade (`log_rotas_test`), não SQLite: o schema usa `CHECK`,
`IDENTITY` e `timestamptz`, e um teste que passa no SQLite não prova nada sobre o banco que
vai rodar na empresa.

Cada teste roda dentro de uma transação com `join_transaction_mode="create_savepoint"`, de
modo que os `commit` dos services viram `RELEASE SAVEPOINT` e o rollback externo limpa tudo.

O que está coberto na Fase 2: primeiro acesso e seu fechamento permanente, login e suas
recusas, separação entre tipo de token, revogação de sessão, permissões por papel, unicidade
de e-mail e a trava do último administrador.

---

## 5. O que vem a seguir

| Fase | Entrega | Critério de pronto |
|---|---|---|
| 3 | Clientes, motoristas, veículos, bases, entregas | Administrador cadastra tudo e lista entregas com filtros |
| 4 | Leaflet, geocodificação, revisão de endereço | Entrega aparece no mapa; endereço ruim é corrigível no pino |
| 5 | Matriz de distância e tempo | Matriz real; fonte da matriz visível na resposta |
| 6 | Agrupamento de paradas + OR-Tools | Teste prova que carga acima da capacidade não entra no veículo |
| 7 | Planejador | Entregas viram rotas revisáveis; nada muda de status antes da confirmação |
| 8 | Painel operacional | Indicadores do dia corretos e mapa da operação |
| 9 | Aplicação do motorista | Rota executada ponta a ponta no celular |
| 10 | Testes das regras críticas e documentação final | Suíte verde; outro desenvolvedor sobe o projeto pelo README |
