from .base import *  # noqa: F401,F403

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Hasher rapido: testes nao precisam da seguranca completa do Argon2/PBKDF2 iterado.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Testes nao devem depender de "collectstatic" ter rodado antes (a manifest storage de
# base.py e para producao, so existe apos esse passo de build). Sem isto, qualquer template
# que use {% static %} falha com "Missing staticfiles manifest entry" num checkout limpo —
# foi exatamente o que quebrou o CI, mascarado localmente por um staticfiles/ antigo em disco.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Turnstile em modo de teste (chaves oficiais de teste da Cloudflare, sempre validas)
TURNSTILE_SITE_KEY = "1x00000000000000000000AA"
TURNSTILE_SECRET_KEY = "1x0000000000000000000000000000000AA"
TURNSTILE_ENABLED = True
