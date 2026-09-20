from ._require import require
from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env

DEBUG = False

# Segredos que DEVEM vir do ambiente em producao. Sem default: se faltar, a aplicacao
# recusa subir (falha alto) em vez de usar silenciosamente um valor de desenvolvimento
# que fica publico no repositorio.
SECRET_KEY = require(env, "SECRET_KEY")
FIELD_ENCRYPTION_KEY = require(env, "FIELD_ENCRYPTION_KEY")
TURNSTILE_SITE_KEY = require(env, "TURNSTILE_SITE_KEY")
TURNSTILE_SECRET_KEY = require(env, "TURNSTILE_SECRET_KEY")
TURNSTILE_ENABLED = True
EMAIL_HOST = require(env, "EMAIL_HOST")
EMAIL_HOST_USER = require(env, "EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = require(env, "EMAIL_HOST_PASSWORD")

# A aplicacao roda no subdominio, nao no dominio raiz (reservado para uma futura pagina
# institucional em lserpsistemas.com.br — ver docs/architecture/decisions.md, ADR-012).
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["uncisal.lserpsistemas.com.br"])

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env("DATABASE_PATH", default=str(BASE_DIR / "db.sqlite3")),
    }
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# O Nginx (no host) e quem termina a conexao TLS recebida da Cloudflare e repassa
# via HTTP para o Gunicorn, informando o protocolo original neste header.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = False  # o redirecionamento HTTP->HTTPS ja e feito pelo Nginx/Cloudflare

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 63072000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=["https://uncisal.lserpsistemas.com.br"],
)
