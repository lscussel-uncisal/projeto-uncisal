# syntax=docker/dockerfile:1

# ---- css stage: compila o Tailwind real a cada build (sem Node, sem CDN, sem eval em runtime) ----
# CLI standalone oficial (https://github.com/tailwindlabs/tailwindcss/releases). Compilar aqui,
# a cada imagem, evita depender de um static/css/app.css commitado ficar desatualizado se
# algum template mudar as classes usadas.
FROM python:3.12-slim AS css-builder

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /usr/local/bin/tailwindcss \
      https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64 \
    && chmod +x /usr/local/bin/tailwindcss

COPY src/templates/ /app/templates/
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
# Sobrescreve o CSS commitado (usado no dev local) pelo compilado agora, sempre em dia com os templates.
COPY --from=css-builder /app/static/css/app.css /app/static/css/app.css

RUN mkdir -p /app/staticfiles /app/media /app/db \
    && chmod +x /app/entrypoint.sh \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz/')" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
