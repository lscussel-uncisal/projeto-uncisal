#!/bin/sh
set -eu

echo "[entrypoint] aplicando migracoes..."
python manage.py migrate --noinput

echo "[entrypoint] coletando arquivos estaticos..."
python manage.py collectstatic --noinput

echo "[entrypoint] iniciando gunicorn..."
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
