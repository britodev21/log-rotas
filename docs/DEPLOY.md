# Colocar no ar (VPS com Docker e Traefik)

Passo a passo para subir o Log Rotas numa VPS que já tem **Docker** e **Traefik**. Escrito para
ser seguido sem conhecer Docker: cada comando diz o que faz e o que você deve ver acontecer.

**Por que HTTPS não é opcional aqui:** o navegador só libera a localização do celular em site
com cadeado. Sem HTTPS, o rastreamento do motorista simplesmente não funciona. O Traefik
resolve isso sozinho, desde que o domínio aponte para a VPS antes de subir.

---

## O que precisa estar pronto antes

| | Como conferir |
|---|---|
| Acesso à VPS por SSH | `ssh usuario@IP-DA-VPS` entra |
| Docker rodando | `docker ps` responde sem erro |
| Traefik rodando | `docker ps` mostra um contêiner traefik |
| Subdomínio apontando | `ping log-rotas.seudominio.com.br` responde o IP da VPS |

O subdomínio é um registro **A** no painel do seu domínio, apontando para o IP da VPS. A
propagação costuma levar minutos, às vezes horas — faça isso primeiro.

---

## 1. Trazer o código

```bash
cd ~
git clone https://github.com/britodev21/log-rotas.git
cd log-rotas
```

## 2. Descobrir o nome da rede do Traefik

O Traefik e o Log Rotas precisam estar na mesma rede interna do Docker para conversarem.

```bash
docker network ls
```

Anote o nome que o seu Traefik usa (costuma ser `traefik`, `web` ou `proxy`). Se tiver dúvida:

```bash
docker inspect traefik --format '{{json .NetworkSettings.Networks}}' | tr ',' '\n'
```

## 3. Preencher a configuração

```bash
cp .env.example .env
nano .env
```

Preencha, no mínimo:

- `DOMINIO` — o subdomínio que você apontou;
- `REDE_TRAEFIK` — o nome descoberto no passo 2;
- `POSTGRES_PASSWORD` e `JWT_SECRET` — gere cada um com `openssl rand -base64 36`;
- `GOOGLE_MAPS_API_KEY` — a chave do Google (veja a restrição por IP no fim deste arquivo).

Confira também `TRAEFIK_ENTRYPOINT` e `TRAEFIK_CERTRESOLVER`: são os nomes que **o seu**
Traefik usa para a porta HTTPS e para o certificado. Os padrões (`websecure` e `letsencrypt`)
são os mais comuns.

> O `.env` fica só na VPS. Ele tem senha e chave paga, e o repositório é público — por isso o
> arquivo é ignorado pelo Git. Nunca cole o conteúdo dele em e-mail, mensagem ou issue.

## 4. Subir

```bash
docker compose up -d --build
```

A primeira vez demora alguns minutos (compila a tela e baixa o solver de rotas). Depois:

```bash
docker compose ps        # os três devem estar "running"; o db, "healthy"
docker compose logs -f api
```

No log da API você deve ver `Migrando o banco...`, as migrações do Alembic e
`Application startup complete`.

O certificado sai sozinho no primeiro acesso ao domínio — pode levar até um minuto. Abra
`https://log-rotas.seudominio.com.br` e confira o cadeado.

## 5. Primeiro acesso

Abra o endereço no navegador: a tela de **primeiro acesso** pede os dados da empresa e cria o
administrador. Depois disso:

1. cadastre a base (o endereço de onde os caminhões saem), veículos e motoristas;
2. crie um usuário para cada motorista — ele entra com o próprio e-mail;
3. no celular do motorista, abra o endereço e toque em **Instalar**.

---

## Atualizar depois

```bash
cd ~/log-rotas
git pull
docker compose up -d --build
```

As migrações do banco rodam sozinhas na subida. Quem estiver com o app aberto **não** é trocado
no meio do caminho: aparece o aviso de versão nova, e a troca acontece quando a pessoa aceita.

## Backup do banco — faça antes de precisar

Um arquivo por dia, guardando os últimos 14:

```bash
mkdir -p ~/backups
crontab -e
```

Acrescente (3h30, meia hora depois da limpeza automática):

```cron
30 3 * * * cd ~/log-rotas && docker compose exec -T db pg_dump -U logrotas log_rotas | gzip > ~/backups/log-rotas-$(date +\%F).sql.gz && find ~/backups -name 'log-rotas-*.sql.gz' -mtime +14 -delete
```

Restaurar (apaga o banco atual e recria a partir do arquivo):

```bash
gunzip -c ~/backups/log-rotas-2026-09-22.sql.gz | docker compose exec -T db psql -U logrotas -d log_rotas
```

> Backup que nunca foi restaurado não é backup. Teste a restauração uma vez, num banco de
> teste, antes de confiar nela.

---

## Quando algo dá errado

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Navegador diz "não seguro" / sem cadeado | O domínio não aponta para a VPS, ou o nome do `certresolver` está errado | `ping` no domínio; `docker logs traefik` mostra o erro do certificado |
| Página abre, mas tudo dá erro | A API não subiu | `docker compose logs api` |
| Erro de banco no log da API | Senha diferente da que criou o banco | O `POSTGRES_PASSWORD` só vale na **primeira** subida; para trocar, veja abaixo |
| Mapa cinza no celular | Cabeçalho de segurança sem os domínios do mapa | Confira `frontend/nginx.conf` (`connect-src`) |
| Ninguém consegue entrar, diz "muitas tentativas" | O IP real não está chegando na API | O `docker-entrada.sh` já usa `--proxy-headers`; confira se o Traefik envia `X-Forwarded-For` |
| "Trânsito não configurado" no planejamento | `GOOGLE_MAPS_API_KEY` vazia ou `TRAFFIC_PROVIDER` diferente de `google` | Corrija o `.env` e `docker compose up -d` |

**Trocar a senha do banco depois de criado:** o `POSTGRES_PASSWORD` só é usado quando o volume
é criado. Para mudar, altere a senha dentro do banco e depois no `.env`:

```bash
docker compose exec db psql -U logrotas -c "ALTER USER logrotas PASSWORD 'nova-senha';"
nano .env && docker compose up -d
```

---

## Depois que estiver no ar

- **Restrinja a chave do Google ao IP da VPS**, no console do Google Cloud (APIs e Serviços →
  Credenciais → sua chave → Restrições de aplicativo → endereços IP). Sem isso, uma chave
  vazada gasta a sua cota.
- **Troque a senha do administrador** se ainda for a do desenvolvimento — a tela avisa.
- **Confira a limpeza automática** em Sistema → Segurança → Guarda dos dados, no dia seguinte:
  deve aparecer uma execução automática.
- **Veja os relatórios depois da primeira semana**: é lá que aparece se o tempo padrão de 60
  minutos por entrega corresponde à realidade.
