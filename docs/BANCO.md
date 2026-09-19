# Banco de dados

PostgreSQL 18. Migrations com Alembic — o schema nunca é alterado à mão.

```bash
cd backend
.venv/Scripts/python.exe -m alembic upgrade head                    # aplicar
.venv/Scripts/python.exe -m alembic revision --autogenerate -m "..." # gerar
.venv/Scripts/python.exe -m alembic downgrade -1                    # desfazer
```

---

## Convenções

| Regra | Motivo |
|---|---|
| `TIMESTAMPTZ` para instantes, sempre UTC | Conversão para o fuso local acontece só na borda |
| `DATE` para a data de operação | É uma data local, não um instante |
| `NUMERIC` para peso e volume | `float` acumula erro ao somar |
| Distância em **metros inteiros**, duração em **segundos inteiros** | `float` acumula erro ao somar 40 trechos |
| Enums como `VARCHAR` + `CHECK` | `ENUM` nativo torna migration dolorosa |
| Valores de enum em ASCII maiúsculo | Acento quebra URL, CSV e integração |
| `created_at` / `updated_at` com `server_default` | Corretos mesmo em INSERT feito fora da aplicação |
| Nomes de constraint via `naming_convention` | Sem isso, o banco gera nomes impossíveis de alterar depois |

---

## Tabelas implementadas (Fases 2 e 3)

### `company_settings`

Configuração da empresa. **Linha única**, garantida por `CHECK (id = 1)`.

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `SMALLINT` PK | sempre 1 |
| `company_name` | `VARCHAR(160)` | obrigatório |
| `document` | `VARCHAR(20)` | CNPJ |
| `phone` | `VARCHAR(30)` | |
| `email` | `VARCHAR(255)` | |
| `timezone` | `VARCHAR(64)` | padrão `America/Campo_Grande` |
| `default_stop_service_minutes` | `INTEGER` | `CHECK > 0`. **Valor estimado**, ver LIMITACOES.md |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | |

### `users`

Quem autentica no sistema. Não confundir com `drivers` (Fase 3): o motorista tem perfil
operacional próprio e pode existir sem login, no caso de terceirizado.

| Coluna | Tipo | Notas |
|---|---|---|
| `id` | `BIGINT IDENTITY` PK | |
| `name` | `VARCHAR(120)` | |
| `email` | `VARCHAR(255)` | índice **único**; `CHECK (email = lower(email))` |
| `password_hash` | `VARCHAR(255)` | Argon2id |
| `role` | `VARCHAR(20)` | `CHECK IN ('ADMIN','MOTORISTA')` |
| `active` | `BOOLEAN` | padrão `true` |
| `email_verified` | `BOOLEAN` | padrão `false`; verificação desligada no MVP |
| `token_version` | `INTEGER` | incrementar revoga todos os tokens do usuário |
| `created_at`, `updated_at` | `TIMESTAMPTZ` | |

A `CHECK` de minúsculas é a garantia real de que `Joao@x.com` e `joao@x.com` não viram duas
contas: a aplicação normaliza na borda, e o banco impede qualquer outro caminho de gravar
diferente.

---

### `bases`, `vehicles`, `drivers`, `customers` — Fase 3

**`bases`** — nome, telefone, `is_default`, `active` + bloco de geocodificação.
A classe do modelo se chama `BaseLocation` para não colidir com a base declarativa do
SQLAlchemy.

**`vehicles`** — `plate` com índice único (normalizada sem máscara, em maiúsculas),
`capacity_weight_kg`, `capacity_volume_m3`, `capacity_length_m`, `max_stops` e `crew_size`.
As quatro capacidades são **anuláveis** de propósito: ainda não se sabe qual limita a operação
da Britto. `CHECK` garante que, quando preenchidas, sejam positivas.

**`drivers`** — `user_id` **anulável e único**, com `ON DELETE SET NULL`: apagar o acesso não
pode apagar o histórico do motorista, que ficará amarrado às rotas executadas.

**`customers`** — dados de contato + bloco de geocodificação, com **índice único parcial** em
`document`:

```sql
CREATE UNIQUE INDEX uq_customers_document ON customers (document)
  WHERE document IS NOT NULL;
```

Um `UNIQUE` comum aceitaria vários `NULL` no Postgres, mas o índice parcial deixa a intenção
explícita e não indexa as linhas sem documento.

### Bloco de geocodificação (`GeocodableMixin`)

Compartilhado por `bases` e `customers`, e por `deliveries` quando ela existir:
`address`, `latitude`, `longitude` (`NUMERIC(9,6)`), `geocode_status`, `geocode_precision`,
`geocode_provider`, `geocode_error`, `geocoded_at`.

`CHECK` garante que latitude e longitude andem **juntas** — uma sem a outra não localiza nada
e seria um estado impossível de interpretar depois — e que estejam dentro da faixa válida.

Status: `PENDENTE | OK | AMBIGUO | FALHOU | MANUAL`. `MANUAL` nunca é sobrescrito pela
geocodificação automática.

---

## Planejamento e execução — Fases 3 a 9

**Implementado.** As decisões abaixo explicam por que cada tabela tem a forma que tem.

### `deliveries`

Além dos dados do pedido, carrega o bloco de geocodificação: `geocode_status`
(`PENDENTE | OK | AMBIGUO | FALHOU | MANUAL`), `geocode_provider`, `geocode_precision`,
`geocode_error`.

Sem esse bloco não dá para distinguir "ainda não geocodifiquei" de "geocodifiquei e falhou" de
"o administrador corrigiu o pino à mão" — e sem essa distinção a tela de revisão de endereços
é impossível. `MANUAL` nunca é sobrescrito por geocodificação automática.

Também carrega `service_time_minutes` (tempo parado na porta), `required_crew` (quantas
pessoas a entrega exige), `order_number` e `invoice_number` (opcionais, para o dia em que
houver vínculo com o sistema de vendas).

### `route_plans`

O resultado de uma execução do otimizador, **antes** de virar rota de verdade.

Existe porque o fluxo exige calcular → revisar → confirmar. Sem essa entidade, o
administrador calcularia e o sistema já teria escrito rotas reais no banco. Guarda também a
matriz usada, sua origem (`OSRM` ou `HAVERSINE`) e as estatísticas do solver, o que torna o
resultado auditável: dá para provar depois por que o sistema montou aquela rota.

Status: `RASCUNHO | CONFIRMADO | DESCARTADO`.

### `routes`

Status: `RASCUNHO | PLANEJADA | INICIADA | FINALIZADA | CANCELADA`.

Um motorista pode ter **várias rotas no mesmo dia** (turnos). A regra real não é "uma por
dia", é "uma em execução por vez", garantida por índices parciais:

```sql
CREATE UNIQUE INDEX ... ON routes (driver_id)  WHERE status = 'INICIADA';
CREATE UNIQUE INDEX ... ON routes (vehicle_id) WHERE status = 'INICIADA';
```

### `route_stops`

A **visita física**, não a entrega.

| Coluna | Por que existe |
|---|---|
| `stop_type` | `BASE_SAIDA \| ENTREGA \| BASE_RECARGA \| BASE_RETORNO` |
| `trip_number` | prepara múltiplas viagens (volta à base para recarregar) |
| `sequence` | `UNIQUE (route_id, sequence)` DEFERRABLE, para reordenar numa transação |
| `arrived_at`, `departed_at` | a visita tem chegada e saída; o resultado é por entrega |

`stop_type` e `trip_number` custam duas colunas hoje e são o que torna o retorno à base
implementável depois **sem migração destrutiva**. No MVP só serão geradas rotas
`BASE_SAIDA → ENTREGA* → BASE_RETORNO` com `trip_number = 1`.

### `route_stop_deliveries`

Liga a parada às entregas que ela resolve — **uma parada pode ter várias entregas** (prédio,
condomínio, galeria: o motorista estaciona uma vez).

Guarda o resultado por entrega: `status`, `delivered_at`, `failure_reason`, `receiver_name`.

Optou-se por esta tabela em vez de um `deliveries.route_stop_id` direto porque a entrega não
entregue volta a ser planejada depois. Com chave estrangeira na entrega, o vínculo com a
tentativa anterior seria sobrescrito e o histórico sumiria. Com a tabela de ligação, cada
planejamento cria um registro novo e a operação consegue provar "tentamos na terça, cliente
ausente; tentamos na quinta, entregue".

### `delivery_events`

Append-only: `from_status`, `to_status`, `reason`, `actor_user_id`, coordenada, instante.

Logística vive de comprovação. "O motorista registrou cliente ausente às 14h32, nesta
coordenada" é informação que a empresa vai precisar contra reclamação — e que a coluna
`status`, por ser sobrescrita, destrói.

### `geocode_cache`

Chaveada por hash do endereço normalizado. Guarda coordenada, precisão, provedor e resposta
bruta.

Sem vínculo com cliente ou entrega: endereço postal é dado público, e o Nominatim limita a uma
requisição por segundo — o recurso mais escasso do MVP. Cachear de forma compartilhada é o que
torna a importação de endereços viável.

### Status das entregas

```
PENDENTE ──► PLANEJADA ──► EM_ROTA ──► CHEGOU ──► ENTREGUE
    ▲            │                        │
    │            │                        └──► NAO_ENTREGUE ──┐
    │            │                                            │
    └────────────┴────────────────────────────────────────────┘
                        (replanejamento / plano descartado)

CANCELADA: a partir de PENDENTE ou PLANEJADA.
```

A validação de transição vive em um único lugar (`services/status_machine.py`). Nenhum
endpoint altera status diretamente — é assim que se evita o estado inconsistente que mata
sistema logístico.

`route_stop_deliveries.status` é a fonte da verdade operacional; `deliveries.status` é uma
projeção atualizada na mesma transação, para que listagem e filtro não precisem de JOIN.
