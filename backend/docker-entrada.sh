#!/bin/sh
# Sobe o backend: migra o banco e então serve.
#
# A migração roda AQUI, num processo só, antes dos workers: se rodasse
# dentro de cada worker, duas cópias do Alembic tentariam alterar a mesma
# tabela ao mesmo tempo. E roda a cada start porque é o que garante que o
# banco em produção tem o formato que este código espera — um deploy com
# migração esquecida quebra na primeira tela que usa a coluna nova.
set -e

echo "Migrando o banco..."
alembic upgrade head

echo "Subindo a API..."
# --proxy-headers: quem chega vem pelo Traefik, então o IP real do visitante
# está no cabeçalho X-Forwarded-For. Sem isto, TODO login parece vir do
# mesmo endereço e o bloqueio por tentativas trancaria a empresa inteira
# (docs/SEGURANCA.md).
#
# --forwarded-allow-ips='*': dentro da rede do Docker o IP do proxy muda a
# cada deploy. É seguro porque este contêiner não fica exposto na internet:
# só o Traefik alcança a porta 8000.
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers "${WORKERS:-2}" \
  --proxy-headers \
  --forwarded-allow-ips='*' \
  --log-level "${LOG_LEVEL:-info}"
