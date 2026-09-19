# Roadmap

Uma fase por vez. Cada uma é entregável e testável sozinha, e termina num critério objetivo.

| Fase | Situação |
|---|---|
| 0 — Esqueleto do projeto | ✅ concluída |
| 1 — Arquitetura | ✅ concluída |
| 2 — Backend base, acesso e usuários | ✅ concluída |
| 3 — Cadastros | 🟡 parcial — falta entregas |
| 4 — Mapa e geocodificação | ⬜ |
| 5 — Distância e tempo | ⬜ |
| 6 — Otimização | ⬜ |
| 7 — Planejador | ⬜ |
| 8 — Painel operacional | ⬜ |
| 9 — Aplicação do motorista | ⬜ |
| 10 — Testes e documentação final | ⬜ |

---

## ✅ Fase 0 — Esqueleto

Estrutura de pastas, `.gitignore`, `.env.example`, dependências fixadas, banco criado.

## ✅ Fase 1 — Arquitetura

Camadas, portas e adaptadores, modelo de dados, estratégia de mapa, geocodificação, routing e
otimização, riscos e escopo. Registrada em [ARQUITETURA.md](ARQUITETURA.md).

## ✅ Fase 2 — Backend base, acesso e usuários

**Entregue:**

- FastAPI em camadas, PostgreSQL, Alembic, configuração por `.env`, CORS, tratamento de erro,
  log e `GET /health`
- Senhas com Argon2id, JWT de acesso e renovação, revogação por `token_version`
- Tela de primeiro acesso (cria empresa + administrador, depois se fecha para sempre)
- Login, renovação de sessão, perfil, troca da própria senha
- Gestão de usuários com papéis `ADMIN` e `MOTORISTA`
- Configuração da empresa
- Frontend: tokens de design em CSS puro, componentes reutilizáveis, casca administrativa e
  casca do motorista (separadas), rotas protegidas por papel
- 25 testes automatizados contra PostgreSQL real

**Critério de pronto atingido:** o administrador entra, cria o acesso de um motorista, e o
motorista recebe 403 em toda rota administrativa.

---

## 🟡 Fase 3 — Cadastros

**Entregue:** clientes, motoristas, veículos e bases — API, regras, migration, 35 testes e as
quatro telas com busca, filtro, criação e edição.

Regras que valem registro:

- a primeira base cadastrada vira a padrão sozinha, e marcar outra desmarca a anterior;
  desativar uma base limpa o `is_default`, porque o planejador a ofereceria e falharia;
- placa é normalizada (sem máscara, maiúscula) antes de gravar — `abc-1234` e `ABC1234` não
  podem virar dois veículos;
- as capacidades do veículo (peso, volume, comprimento, paradas) são **todas opcionais**,
  porque ainda não se sabe qual limita a operação da Britto. Cada uma preenchida pode virar
  restrição no solver da Fase 6; as vazias são ignoradas;
- motorista existe sem acesso ao sistema (terceirizado), mas vincular um usuário administrador
  a um perfil de motorista é recusado — ele passaria a aparecer como quem leva carga;
- **trocar o endereço descarta a coordenada** e devolve o registro para a fila de
  geocodificação. Sem essa regra, editar "Rua A, 100" para "Rua B, 500" manteria o pino na
  Rua A e a rota seria calculada para o endereço errado, sem aviso. Coordenada informada à
  mão vira `MANUAL` e a geocodificação automática nunca a sobrescreve.

**Falta:** o cadastro de entregas.

**Por que ficou para depois:** a entrega é a entidade que depende das respostas sobre a
operação — o que limita a carga, se há instalação e quanto dura, quantas pessoas cada serviço
exige. Modelá-la sobre suposição significaria acertar o schema da tabela que mais terá dados
por sorte. Ver [LIMITACOES.md](LIMITACOES.md) § 2.

## ⬜ Fase 4 — Mapa e geocodificação

Leaflet com OpenStreetMap dentro da aplicação, provider de geocodificação atrás de interface,
cache em banco, fila de revisão de endereço e ajuste manual do pino.

**Pronto quando:** uma entrega cadastrada aparece no mapa, e um endereço que o provedor não
resolveu pode ser corrigido arrastando o pino.

## ⬜ Fase 5 — Distância e tempo

`MatrixProvider` com adaptador OSRM e fallback em linha reta, sempre rotulado como estimativa.

**Pronto quando:** a matriz de uma operação real é calculada e a resposta informa de onde ela
veio.

## ⬜ Fase 6 — Otimização

Agrupamento de entregas em paradas (uma parada pode ter várias entregas) e OR-Tools com
dimensão principal de **tempo**.

**Pronto quando:** um teste prova que carga acima da capacidade não entra no veículo, e que o
excedente volta como não atribuído em vez de ser espremido na rota.

## ⬜ Fase 7 — Planejador

Selecionar data, base, entregas, veículos e motoristas; calcular; revisar no mapa; confirmar.

**Pronto quando:** as entregas de um dia viram rotas revisáveis e **nada muda de status antes
da confirmação**.

## ⬜ Fase 8 — Painel operacional

Indicadores do dia e mapa da operação, substituindo a tela de andamento da implantação.

## ⬜ Fase 9 — Aplicação do motorista

Rota do dia, próxima parada, mapa, botões grandes, motivos de insucesso, observação e
encerramento.

**Bloqueio conhecido:** geolocalização exige HTTPS. Precisa ser resolvido antes desta fase —
ver [LIMITACOES.md](LIMITACOES.md) § 4.1.

## ⬜ Fase 10 — Testes e documentação final

---

## Fora do escopo, sem impedimento futuro

Múltiplas viagens com recarga na base · janelas de horário ativas no solver · prioridade
influenciando a otimização · GPS contínuo · WebSocket · foto, assinatura e código de barras ·
importação CSV · notificações e WhatsApp · relatórios · aplicativo nativo · Docker e deploy.

O modelo de dados já reserva espaço para os quatro primeiros (`trip_number`, `stop_type`,
`time_window_*`, `priority`), sem implementá-los.
