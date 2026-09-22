# Segurança

As políticas em vigor, o porquê de cada uma, e o que o servidor web precisa fazer em produção.
A tela **Sistema → Segurança** mostra as regras lidas da configuração, as contas bloqueadas e os
eventos recentes.

---

## Senhas

Segue o NIST SP 800-63B — o que se recomendava há quinze anos foi abandonado, e por bons motivos.

| Regra | Por quê |
|---|---|
| **Mínimo de 10 caracteres** | Comprimento é o que mais pesa na força de uma senha. |
| **Recusa senhas conhecidas** | O que um invasor tenta primeiro. Inclui palavra comum + números (`Flamengo@2024`), sequências (`1234567890ab`, `qwerty12345`) e repetição. |
| **Recusa o contexto** | Nome da pessoa, parte do e-mail, `britto`, `logrotas`. |
| **Não exige** maiúscula, número e símbolo | Essa regra produz `Senha@2024`: cumpre a exigência e está em toda lista de senhas vazadas. Uma frase — *"pão de queijo quente"* — é mais forte e mais fácil de lembrar. |
| **Não exige** troca periódica | Força variações previsíveis (`Britto2025` → `Britto2026`). Troca-se quando há motivo. |

Vale nos quatro caminhos por onde uma senha entra: primeiro acesso, criação de usuário, troca da
própria senha e redefinição pelo administrador. Todos os problemas da senha aparecem de uma vez.

**Senhas antigas continuam entrando.** Trancar alguém fora por uma regra nova seria pior. Mas, se a
senha usada no login não passaria na política de hoje, a tela mostra um aviso até ela ser trocada
(em **Minha conta**, no menu do usuário ou no ícone de chave do motorista).

`SenhaForte123` está na lista de recusadas por um motivo concreto: era a senha dos testes deste
repositório, que é público. **O administrador que ainda a usa verá o aviso — troque.**

Implementação: `backend/app/core/senha.py`.

---

## Tentativas de login

| Regra | Valor padrão | Configuração |
|---|---|---|
| Falhas na **mesma conta** que bloqueiam a conta | 5 em 15 min | `LOGIN_MAX_FALHAS_CONTA`, `LOGIN_JANELA_MINUTOS` |
| Falhas do **mesmo IP**, em qualquer conta, que bloqueiam o IP | 20 em 15 min | `LOGIN_MAX_FALHAS_IP` |
| Duração do bloqueio | 15 min | `LOGIN_BLOQUEIO_MINUTOS` |

As decisões que não são óbvias:

- **Dois limites porque são dois ataques.** Adivinhar a senha de uma pessoa (muitas tentativas numa
  conta) e testar uma senha comum em muitas contas (uma tentativa em cada — o limite por conta
  sozinho nunca dispararia). O do IP é mais alto porque um escritório inteiro pode sair pelo mesmo
  endereço.
- **Vale para e-mail que não existe**, com a mesma mensagem. Bloquear só conta existente revelaria,
  pelo comportamento, quais contas existem.
- **Durante o bloqueio, nem a senha certa entra.** Se entrasse, não seria bloqueio: bastaria acertar
  dentro dele.
- **Insistir durante o bloqueio não o prolonga.** Senão, quem ataca manteria o dono da conta
  trancado para sempre, só insistindo.
- **Login certo zera a contagem.** O administrador também pode liberar uma conta antes do tempo,
  na tela de Segurança — fica registrado quem liberou.
- **A contagem fica no banco, não na memória:** reiniciar o servidor não zera a contagem de quem
  está tentando adivinhar uma senha, e com vários processos todos veem as mesmas tentativas.

A resposta do bloqueio é **429** com `Retry-After`, e a tela diz quanto falta.

**Em produção atrás do nginx**, o uvicorn precisa rodar com `--proxy-headers
--forwarded-allow-ips=127.0.0.1`. Sem isso, todo login parece vir do IP do próprio nginx — e 20
erros de qualquer pessoa bloqueariam **todo mundo**.

Implementação: `backend/app/services/seguranca_service.py`.

---

## Sessão

| | |
|---|---|
| Token de acesso | 60 min (`ACCESS_TOKEN_EXPIRE_MINUTES`) |
| Renovação automática | até 7 dias (`REFRESH_TOKEN_EXPIRE_DAYS`) |
| Trocar a senha | encerra todas as outras sessões na hora |
| Redefinição pelo admin, desativação | encerra todas as sessões do usuário na hora |

O encerramento imediato usa `token_version`: cada token carrega a versão; mudar a versão invalida
todos os tokens emitidos antes.

**Limite conhecido:** o token fica no `localStorage`, onde um script injetado poderia lê-lo. A
Content-Security-Policy abaixo é a proteção contra isso — ela impede que script de fora rode na
página. Cookie `httpOnly` seria mais forte, mas complicaria o aplicativo nativo previsto.

---

## Registro de eventos

O que fica gravado em `security_events`, com quem fez, sobre quem, quando e de que IP:

| Evento | Quando |
|---|---|
| Conta bloqueada por tentativas | Na falha que atinge o limite |
| IP bloqueado por tentativas | Idem, para o IP |
| Conta desbloqueada | O admin liberou antes do tempo |
| Trocou a própria senha | Pela tela Minha conta |
| Senha redefinida por administrador | Pelo cadastro de usuários |
| Usuário criado | Com o papel |
| Papel alterado | De qual para qual |
| Usuário desativado / reativado | |

Cada tentativa de login também fica em `login_attempts` (e-mail, IP, navegador, resultado).

---

## Cabeçalhos

**API** (`backend/app/main.py`), em toda resposta:

| Cabeçalho | Efeito |
|---|---|
| `X-Content-Type-Options: nosniff` | O navegador não "adivinha" que um JSON é HTML e o executa |
| `X-Frame-Options: DENY` | Ninguém embute a API ou o `/docs` num iframe |
| `Referrer-Policy: strict-origin-when-cross-origin` | Endereços internos não vazam para outros sites |
| `Cache-Control: no-store` (em `/api/`) | Token e dado de cliente não ficam em cache |
| `Strict-Transport-Security` | **Só com `HSTS=true`**, e só quando houver HTTPS de verdade |

**Tela** (`frontend/vite.config.js`, `CABECALHOS_PRODUCAO`): Content-Security-Policy estrita, que
permite exatamente o que a tela usa — as fontes do Google, os ladrilhos da Esri e a própria API — e
nada mais. Sem script embutido, sem estilo embutido, sem iframe.

Conferido no build de produção, com a política ativa: painel com mapa, página de segurança, troca
de senha e tela do motorista — **nenhuma violação**. Duas coisas precisaram mudar para isso: o
script do tema saiu do `index.html` para `public/tema-inicial.js`, e os marcadores do mapa passaram
a receber a cor por classe CSS em vez de `style=""` — com a política ativa, **eles perdiam a cor**.
Esse defeito só aparece no build de produção: no modo de desenvolvimento a política fica desligada,
porque o recarregamento a quente do React depende de script embutido.

**Toda mudança que carregar recurso de outro lugar precisa entrar na política** — senão será
bloqueada em produção sem aviso no desenvolvimento. Teste com `npm run build && npx vite preview`.

### nginx em produção

Os mesmos cabeçalhos do `vite.config.js`:

```nginx
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob: https://services.arcgisonline.com; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Permissions-Policy "geolocation=(self), screen-wake-lock=(self), camera=(), microphone=()" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

E no backend: `HSTS=true` no `.env` só depois que o HTTPS estiver funcionando.

---

## Guarda dos dados

| Dado | Mantido por | Configuração |
|---|---|---|
| Posições do GPS dos motoristas | 90 dias | `RETENCAO_POSICOES_DIAS` |
| Tentativas de login | 180 dias | `RETENCAO_TENTATIVAS_LOGIN_DIAS` |
| Eventos de segurança | 730 dias | `RETENCAO_EVENTOS_SEGURANCA_DIAS` |
| Endereço que falhou na busca | 30 dias | fixo — depois disso é tentado de novo |

A posição do motorista é dado pessoal (LGPD): só é recebida com a rota em andamento, e não é
guardada para sempre. Os eventos ficam mais tempo porque respondem perguntas que só aparecem muito
depois ("quem promoveu este usuário a administrador?").

A limpeza roda sozinha todo dia a partir das 3h (`LIMPEZA_HORA`; `-1` desliga). Cada execução
fica registrada e aparece na tela de Segurança, em **Guarda dos dados**, com o botão **Limpar
agora**. Detalhes em `docs/LIMITACOES.md`, seção 3.9.

---

## O que ainda não existe

- **Verificação de e-mail e recuperação de senha por e-mail.** Não há cadastro público; quem
  esquece a senha pede ao administrador, que a redefine (e fica registrado).
- **Segundo fator (2FA).** Recomendável para administradores quando o sistema estiver na internet.
- **Limite de tentativas na troca de senha.** Exige estar logado, o que já limita muito; entra junto
  com o 2FA.
- **Rotação do token de renovação com detecção de reuso.**
