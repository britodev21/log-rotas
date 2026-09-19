# Roadmap

| Fase | Situação |
|---|---|
| 0 — Esqueleto do projeto | ✅ |
| 1 — Arquitetura | ✅ |
| 2 — Backend base, acesso e usuários | ✅ |
| 3 — Cadastros e entregas | ✅ |
| 4 — Geocodificação e mapa | ✅ |
| 5 — Distância e tempo | ✅ |
| 6 — Otimização | ✅ |
| 7 — Planejador | ✅ |
| 8 — Painel operacional | ✅ |
| 9 — Aplicação do motorista | ✅ |
| 10 — Testes e documentação | ✅ |

O fluxo completo funciona ponta a ponta: cadastrar → geocodificar → planejar →
confirmar → executar no celular → acompanhar no painel.

O que **não** está pronto para a empresa depender do sistema está em
[LIMITACOES.md](LIMITACOES.md) — leia antes de colocar em produção.

---

## O que cada fase entregou

### ✅ Fase 2 — Acesso

FastAPI em camadas, PostgreSQL com Alembic, Argon2id, JWT de acesso e renovação com revogação
por `token_version`, tela de primeiro acesso que se fecha depois do primeiro usuário, papéis
`ADMIN` e `MOTORISTA`.

### ✅ Fase 3 — Cadastros e entregas

Clientes, motoristas, veículos e bases. Entregas com o bloco de geocodificação, medidas
opcionais, prioridade, janela de horário e equipe necessária.

**Máquina de estados** num módulo único: nenhum endpoint altera `status` diretamente.
`delivery_events` grava cada transição, append-only, com hora, motivo, autor e coordenada.

### ✅ Fase 4 — Geocodificação

Porta `GeocodingProvider` com adaptador Nominatim, cache por endereço normalizado e fila de
revisão com ajuste do pino no mapa.

Quatro desfechos distintos — `OK`, `AMBIGUO`, `FALHOU`, `ERRO_PROVEDOR` — e a distinção é o
que torna a fila possível. **Ambíguo não grava coordenada:** escolher entre candidatos é o
caminho mais curto para entregar no lugar errado.

### ✅ Fase 5 — Distância e tempo

Porta `MatrixProvider` com OSRM e fallback Haversine. A matriz **carrega a própria origem**, e
essa marcação atravessa o plano, a API e a tela.

### ✅ Fase 6 — Otimização

OR-Tools com dimensão principal de **tempo**, não quilometragem — numa operação dentro de
Campo Grande é o tempo parado que limita o dia.

Agrupamento de entregas em paradas antes da matriz: o motorista estaciona uma vez.

### ✅ Fase 7 — Planejador

Selecionar → calcular → revisar no mapa → confirmar. **Calcular não muda a operação.**

### ✅ Fase 8 — Painel

Indicadores reais do dia, rotas ativas desenhadas no mapa e progresso por motorista, com
atualização a cada 15 segundos.

### ✅ Fase 9 — Motorista

Rota do dia no celular: iniciar, chegar, entregar, registrar insucesso com motivo, finalizar.
Alvos de toque de 48px, coordenada opcional em todo registro.

### ✅ Fase 10 — Testes

149 testes contra PostgreSQL real, cobrindo o que dói quando quebra: isolamento entre
motoristas, máquina de estados, capacidade no solver, agrupamento, e a regra de que finalizar
não marca como entregue o que ficou sem registro.

---

## Três bugs que os testes encontraram

Vale registrar, porque nenhum deles quebrava a tela — todos produziriam dado errado em
silêncio.

**1. Confirmar duas vezes passava.** A máquina de estados tratava `de == para` como
idempotente. Confirmar um planejamento duas vezes gravava eventos duplicados no histórico e
reatribuía motoristas. Regravar o mesmo status passou a ser recusado.

**2. `dict()` sobre um `Result` do SQLAlchemy.** O `Result` tem método `keys()`, então `dict()`
o trata como mapa e tenta indexá-lo. `TypeError` em tempo de execução, no painel. Faltava
`.all()`.

**3. Agrupamento exigia endereço idêntico.** Duas entregas na mesma coordenada com o texto do
endereço escrito de formas diferentes viravam duas paradas — o motorista estacionaria duas
vezes no mesmo lugar. O critério passou a ser a **posição**, quando a coordenada é confiável
(`EXATO` ou `MANUAL`); com coordenada grosseira o endereço volta à chave, para não juntar
entregas a quarteirões de distância.

---

## Fora do escopo, sem impedimento futuro

Múltiplas viagens com recarga na base · janelas de horário ativas por padrão · GPS contínuo ·
WebSocket · foto, assinatura e código de barras · importação CSV · notificações e WhatsApp ·
relatórios · aplicativo nativo · Docker e deploy.

O modelo de dados já reserva espaço para os primeiros: `trip_number` e `stop_type` preveem o
retorno à base para recarregar, e `time_window_*` já é respeitado pelo solver quando
preenchido.
