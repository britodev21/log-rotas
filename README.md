# Log Rotas

Sistema de planejamento e execução de rotas de entrega da **Britto Móveis e Corrimão**.

O administrador cadastra entregas, veículos, motoristas e a base da operação. O sistema
geocodifica os endereços, calcula distâncias e tempos reais, distribui as entregas entre os
veículos respeitando restrições, encontra uma sequência otimizada de paradas, mostra tudo em
um mapa dentro da própria aplicação e entrega a rota pronta ao motorista, que a executa pelo
celular e atualiza o status de cada entrega.

> **Estado atual: fluxo completo funcionando.**
> Cadastrar → geocodificar → planejar → confirmar → executar no celular → acompanhar no painel.
> 42 endpoints, 149 testes contra PostgreSQL real.
>
> O que ainda precisa ser resolvido **antes de a empresa depender do sistema** está em
> [docs/LIMITACOES.md](docs/LIMITACOES.md) — principalmente a troca dos provedores externos
> gratuitos e o HTTPS para a geolocalização do motorista.

---

## Sumário

- [Requisitos](#requisitos)
- [Instalação](#instalação)
- [Como executar](#como-executar)
- [Primeiro acesso](#primeiro-acesso)
- [Configuração (.env)](#configuração-env)
- [Testes](#testes)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Documentação](#documentação)

---

## Requisitos

| Ferramenta | Versão testada | Observação |
|---|---|---|
| Python | 3.14.5 | Todas as dependências têm wheel para cp314 no Windows |
| Node.js | 24.16 | Com npm 11 |
| PostgreSQL | 18.4 | Rodando em `localhost:5432` |

Docker não é necessário. O projeto roda inteiro na máquina local, sem nenhum serviço pago.

---

## Instalação

### 1. Banco de dados

```bash
psql -U postgres -c "CREATE DATABASE log_rotas ENCODING 'UTF8'"
psql -U postgres -c "CREATE DATABASE log_rotas_test ENCODING 'UTF8'"
```

O segundo banco é usado apenas pelos testes automatizados, que o limpam a cada execução.

### 2. Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt  # Linux/macOS

cp .env.example .env
```

Gere um segredo próprio para o JWT e coloque em `JWT_SECRET` dentro do `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Aplique as migrations:

```bash
.venv/Scripts/python.exe -m alembic upgrade head
```

### 3. Frontend

```bash
cd frontend
npm install
```

---

## Como executar

Dois terminais.

**Backend** (porta 8000):

```bash
cd backend
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

- API: <http://localhost:8000>
- Documentação interativa: <http://localhost:8000/docs>
- Saúde da aplicação: <http://localhost:8000/health>

**Frontend** (porta 5173):

```bash
cd frontend
npm run dev
```

- Aplicação: <http://localhost:5173>

O servidor de desenvolvimento do Vite encaminha `/api` para o backend, então não há CORS
durante o desenvolvimento.

---

## Primeiro acesso

O Log Rotas **não tem cadastro público**: é a aplicação de uma empresa só. Na primeira
execução, enquanto não existe nenhum usuário, a aplicação abre a tela de primeiro acesso,
onde você cria a empresa e o administrador inicial.

Depois desse administrador, a tela se fecha para sempre e novos acessos passam a ser criados
por ele, em **Usuários**. Cada motorista precisa de um acesso próprio para receber a rota no
celular.

---

## Configuração (.env)

O arquivo `.env` **nunca** vai para o git. Use `backend/.env.example` como base.

| Variável | Para que serve |
|---|---|
| `DATABASE_URL` | Conexão com o PostgreSQL |
| `JWT_SECRET` | Segredo que assina os tokens. Mínimo de 32 caracteres |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Validade do token de acesso (padrão: 60) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Validade do token de renovação (padrão: 7) |
| `CORS_ORIGINS` | Origens autorizadas, separadas por vírgula |
| `DEFAULT_TIMEZONE` | Fuso da operação (`America/Campo_Grande`) |
| `DEFAULT_STOP_SERVICE_MINUTES` | Tempo padrão parado em cada entrega |
| `GEOCODING_PROVIDER`, `NOMINATIM_*` | Geocodificação de endereços |
| `MATRIX_PROVIDER`, `OSRM_BASE_URL` | Distância e tempo. `haversine` força a estimativa local |

A aplicação se recusa a subir com `JWT_SECRET` ausente ou curto demais, e se recusa a subir
em produção com o segredo de exemplo.

---

## Instalar no celular

A tela é um **PWA**: no Chrome do Android, o próprio app oferece "Instalar"; no iPhone, é
**Compartilhar → Adicionar à Tela de Início**. Instalado, abre pelo ícone, em tela cheia, e
continua abrindo onde o sinal é ruim — a última versão fica guardada no aparelho, junto com os
ladrilhos do mapa já vistos.

Quando uma versão nova é publicada, o app **avisa e espera**: a troca só acontece quando a
pessoa aceita, para não trocar o código embaixo de um motorista no meio da entrega.

O que ele **não** faz: GPS com a tela apagada, registro de entrega sem sinal e notificações.
Isso exige aplicativo empacotado — ver `docs/LIMITACOES.md`, 3.11.

Em produção o `nginx` precisa servir `sw.js` e `manifest.webmanifest` **sem cache longo**,
senão o aparelho segura a versão antiga:

```nginx
location = /sw.js                { add_header Cache-Control "no-cache"; }
location = /manifest.webmanifest { add_header Cache-Control "no-cache"; }
```

---

## Testes

```bash
cd backend
.venv/Scripts/python.exe -m pytest
```

149 testes contra um PostgreSQL de verdade (`log_rotas_test`), não contra SQLite: o schema
usa `CHECK`, `IDENTITY`, índices parciais e `timestamptz`, e um teste que passa no SQLite não
prova nada sobre o banco que vai rodar na empresa. Cada teste roda dentro de uma transação
revertida ao final, então o banco volta limpo mesmo com os serviços fazendo `commit`.

A suíte **não toca a rede**: o provedor de matriz é fixado em `haversine` e a geocodificação
usa um provedor falso. O que se verifica não é se o Nominatim funciona — é o que o Log Rotas
faz com cada resposta possível.

O que está coberto é o que dói quando quebra: isolamento entre motoristas, máquina de estados,
capacidade no solver, agrupamento de paradas, e a regra de que finalizar uma rota **não**
marca como entregue o que ficou sem registro.

Lint e formatação:

```bash
.venv/Scripts/python.exe -m ruff check app tests
.venv/Scripts/python.exe -m ruff format app tests
```

---

## Estrutura do projeto

```
log-rotas/
├─ backend/
│  ├─ alembic/            migrations
│  ├─ app/
│  │  ├─ api/             camada HTTP: routers e dependências
│  │  ├─ core/            configuração, segurança, erros, enums, log
│  │  ├─ db/              base declarativa e sessão
│  │  ├─ models/          tabelas (SQLAlchemy), sem regra de negócio
│  │  ├─ schemas/         contrato HTTP (Pydantic)
│  │  ├─ repositories/    única camada que monta SQL
│  │  ├─ services/        regra de negócio e controle de transação
│  │  ├─ geocoding/       endereço → coordenada (porta + Nominatim)
│  │  ├─ routing/         distância e tempo (porta + OSRM + Haversine)
│  │  ├─ optimization/    OR-Tools; dataclasses puras, sem banco nem HTTP
│  │  └─ main.py
│  └─ tests/
└─ frontend/
   └─ src/
      ├─ api/             cliente HTTP e chamadas por domínio
      ├─ components/ui/   componentes reutilizáveis
      ├─ contexts/        estado de autenticação
      ├─ hooks/
      ├─ components/map/  Leaflet: mapa, marcadores, trajetos
      ├─ layouts/         casca do admin e casca do motorista
      ├─ pages/
      ├─ routes/
      ├─ styles/          tokens e base (CSS puro)
      └─ utils/           formatação e decodificação de polyline
```

**O módulo de otimização não importa SQLAlchemy nem FastAPI.** Recebe dataclasses puras e
devolve dataclasses puras — é o que permite testá-lo sem banco e trocá-lo sem tocar no resto.

---

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/ARQUITETURA.md](docs/ARQUITETURA.md) | Decisões técnicas e por que foram tomadas |
| [docs/BANCO.md](docs/BANCO.md) | Modelo de dados atual e o modelo planejado |
| [docs/API.md](docs/API.md) | Endpoints disponíveis |
| [docs/LIMITACOES.md](docs/LIMITACOES.md) | **O que ainda não existe e o que é estimativa** |
| [docs/SERVICOS_EXTERNOS.md](docs/SERVICOS_EXTERNOS.md) | Cada serviço externo: para quê, chave, custo, o que acontece quando cai |
| [docs/SEGURANCA.md](docs/SEGURANCA.md) | Senhas, bloqueio por tentativas, sessão, cabeçalhos, guarda dos dados |
| [docs/DEPLOY.md](docs/DEPLOY.md) | Colocar no ar numa VPS com Docker e Traefik, passo a passo |
| [docs/ROADMAP.md](docs/ROADMAP.md) | Fases do projeto e o que entra em cada uma |
