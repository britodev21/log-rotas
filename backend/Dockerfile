# Backend do Log Rotas: FastAPI + OR-Tools.
#
# Python 3.13, e não a última versão: o OR-Tools publica os pacotes prontos
# (wheels) com atraso de uma ou duas versões, e sem eles a imagem tentaria
# compilar um solver em C++ dentro do contêiner.
FROM python:3.13-slim

# - PYTHONUNBUFFERED: o log aparece na hora no `docker logs`, e não em blocos.
# - PYTHONDONTWRITEBYTECODE: .pyc não serve para nada num contêiner.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# As dependências primeiro, em camada própria: enquanto o requirements.txt
# não mudar, o build seguinte reaproveita esta camada e não baixa tudo de novo.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY docker-entrada.sh /usr/local/bin/docker-entrada.sh
RUN chmod +x /usr/local/bin/docker-entrada.sh

# Compila tudo aqui: se alguma sintaxe não existir nesta versão do Python, o
# BUILD falha com o arquivo e a linha. Sem isto, o erro só aparece quando o
# contêiner sobe em produção e reinicia em laço — foi o que aconteceu na
# primeira subida, com uma sintaxe que só existe no Python 3.14.
RUN python -m compileall -q app

# Não roda como root: se um dia alguém escapar da aplicação, escapa para um
# usuário sem poder nenhum.
RUN useradd --create-home --uid 10001 logrotas && chown -R logrotas /app
USER logrotas

EXPOSE 8000
ENTRYPOINT ["/usr/local/bin/docker-entrada.sh"]
