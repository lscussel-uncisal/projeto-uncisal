# syntax=docker/dockerfile:1

# ---- css stage: compila o Tailwind real a cada build (sem Node, sem CDN, sem eval em runtime) ----
# CLI standalone oficial (https://github.com/tailwindlabs/tailwindcss/releases). Compilar aqui,
# a cada imagem, evita depender de um static/css/app.css commitado ficar desatualizado se
# algum template mudar as classes usadas.
FROM python:3.12-slim AS css-builder

# Preenchido automaticamente pelo BuildKit (amd64 numa VM Oracle E2/AMD, arm64 numa Ampere A1 —
# ver docs/infra/oracle-cloud-setup.md). Sem isto, o binario ficaria fixo para uma arquitetura so.
ARG TARGETARCH

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN case "${TARGETARCH}" in \
      amd64) TW_ARCH=x64 ;; \
      arm64) TW_ARCH=arm64 ;; \
      *) echo "Arquitetura nao suportada: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && curl -fsSL -o /usr/local/bin/tailwindcss \
      "https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-${TW_ARCH}" \
    && chmod +x /usr/local/bin/tailwindcss

COPY src/templates/ /app/templates/
COPY src/apps/ /app/apps/
COPY src/tailwind/input.css /app/tailwind/input.css

RUN mkdir -p /app/static/css \
    && tailwindcss -i /app/tailwind/input.css -o /app/static/css/app.css --minify

# ---- build stage: instala dependencias em um virtualenv isolado ----
FROM python:3.12-slim AS builder

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install -r requirements.txt

# ---- runtime stage: imagem final, minima e sem usuario root ----
FROM python:3.12-slim

RUN groupadd --system app && useradd --system --gid app --home /app app

WORKDIR /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

COPY --from=builder /opt/venv /opt/venv
COPY src/ /app/
COPY docker/entrypoint.sh /app/entrypoint.sh
COPY docker/scripts/backup-scheduler.sh /app/backup-scheduler.sh
# Sobrescreve o CSS commitado (usado no dev local) pelo compilado agora, sempre em dia com os templates.
COPY --from=css-builder /app/static/css/app.css /app/static/css/app.css

RUN mkdir -p /app/staticfiles /app/media /app/db \
    && chmod +x /app/entrypoint.sh /app/backup-scheduler.sh \
    && chown -R app:app /app

USER app

EXPOSE 8000

# O Host default do urlopen ("127.0.0.1") nao esta em ALLOWED_HOSTS em producao (de proposito,
# ver config/settings/prod.py) - sem o header abaixo o Django devolve 400 e o healthcheck
# fica sempre "unhealthy" mesmo com a aplicacao respondendo normalmente. Le ALLOWED_HOSTS do
# proprio ambiente do container em vez de fixar um dominio, para funcionar em qualquer settings.
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python -c "\
import os, urllib.request; \
host = os.environ.get('ALLOWED_HOSTS', 'localhost').split(',')[0]; \
req = urllib.request.Request('http://127.0.0.1:8000/healthz/', headers={'Host': host}); \
urllib.request.urlopen(req, timeout=2)" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
