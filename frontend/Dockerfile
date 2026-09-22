# Tela do Log Rotas: compila com Node, serve com nginx.
#
# Duas etapas: o Node só existe para gerar os arquivos do site; a imagem que
# vai para a VPS leva apenas o resultado e o nginx (~50 MB em vez de ~1 GB).

FROM node:22-alpine AS construcao
WORKDIR /app

COPY package.json package-lock.json* ./
# `npm ci` instala exatamente o que está no package-lock: build de produção
# não pode resolver versões de novo e trazer algo diferente do testado.
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=construcao /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
