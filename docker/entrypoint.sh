#!/bin/sh
set -eu

echo "[entrypoint] aplicando migracoes..."
python manage.py migrate --noinput

echo "[entrypoint] coletando arquivos estaticos..."
python manage.py collectstatic --noinput

WORKERS="${GUNICORN_WORKERS:-3}"
echo "[entrypoint] iniciando gunicorn com ${WORKERS} worker(s)..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers "${WORKERS}"
