"""
Homologacao: mesmo comportamento de producao, exceto o destino do e-mail.

Existe para testar o FLUXO real de envio (SMTP de verdade, HTML renderizado, assunto,
anexos se houver) sem tocar na conta Gmail de producao nem nos alertas de usuarios reais.

Uso: DJANGO_SETTINGS_MODULE=config.settings.staging

EMAIL_HOST/PORT/USER/PASSWORD devem apontar para uma "caixa de areia" SMTP, nao para o Gmail:
- Mailtrap (https://mailtrap.io) — mesma ferramenta que o Laravel usa; funciona identico aqui,
  Django so enxerga SMTP host/porta/usuario/senha. Plano gratuito, sandbox por projeto.
- Mailpit (https://github.com/axllent/mailpit) — alternativa self-hosted, sem depender de
  conta externa: `docker run -p 1025:1025 -p 8025:8025 axllent/mailpit`, depois
  EMAIL_HOST=localhost EMAIL_PORT=1025 EMAIL_USE_TLS=False (ve os e-mails em
  http://localhost:8025, sem nenhum criar/configurar conta).

Nenhuma das duas chaves fica com default aqui — sem elas configuradas no .env, o fail-fast do
require() evita enviar e-mail de teste sem querer para uma caixa real.

Turnstile continua opcional aqui (herda o comportamento de base.py: TURNSTILE_ENABLED so liga se
as chaves estiverem definidas). Para testar o fluxo completo, use as chaves OFICIAIS DE TESTE da
Cloudflare (sempre validam, nunca sao a chave real do dominio):
  TURNSTILE_SITE_KEY=1x00000000000000000000AA
  TURNSTILE_SECRET_KEY=1x0000000000000000000000000000000AA
"""

from ._require import require
from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env

DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = require(env, "EMAIL_HOST")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
