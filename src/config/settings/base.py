"""
Configuracoes compartilhadas por todos os ambientes.
Ambientes especificos (dev/test/prod) herdam e sobrescrevem o necessario.
"""

from pathlib import Path

import environ

# src/config/settings/base.py -> BASE_DIR aponta para "src/"
BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BASE_DIR.parent

env = environ.Env()
environ.Env.read_env(REPO_ROOT / ".env")

SECRET_KEY = env("SECRET_KEY", default="inseguro-somente-para-desenvolvimento")

# Chave separada da SECRET_KEY, usada apenas para criptografar campos sensiveis em repouso
# (ver apps/core/fields.py). Mantida separada de proposito: rotacionar a SECRET_KEY (ex. apos
# um incidente) nao deve, sozinho, tornar ilegiveis dados ja criptografados no banco.
# Valor abaixo e SOMENTE de desenvolvimento; em producao e exigido via ambiente (config/settings/prod.py).
FIELD_ENCRYPTION_KEY = env(
    "FIELD_ENCRYPTION_KEY", default="O5YpLmxwY3gpkaMKYcVoTyIs4tO03ltk1SQ7TvmONNc="
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps do projeto
    "apps.core",
    "apps.accounts",
    "apps.tickets",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

AUTH_USER_MODEL = "accounts.User"

# Argon2id primeiro (recomendado pela OWASP para hashing de senha); os demais ficam
# apenas para permitir a verificacao de hashes antigos, nunca sao usados para gerar novos.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "tickets:list"
LOGOUT_REDIRECT_URL = "accounts:login"

# Sessao expira por INATIVIDADE, nao só por tempo fixo desde o login: SESSION_SAVE_EVERY_REQUEST
# renova a expiração a cada requisição, entao SESSION_COOKIE_AGE conta a partir da última ação
# do usuário, não do momento do login. Ver ADR de sessão em docs/architecture/decisions.md.
SESSION_COOKIE_AGE = 60 * 30  # 30 minutos de inatividade
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Maceio"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Integracoes especificas do projeto ---
# Sem valor definido, fica "" em desenvolvimento — nao existe chave "de mentira" chumbada
# aqui. TURNSTILE_ENABLED nasce False nesse caso, e o formulario de login/cadastro nao deve
# renderizar nem validar o widget. Em producao, config/settings/prod.py exige as duas chaves
# (require()) e forca TURNSTILE_ENABLED = True.
TURNSTILE_SITE_KEY = env("TURNSTILE_SITE_KEY", default="")
TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY", default="")
TURNSTILE_ENABLED = bool(TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY)
OTP_ISSUER_NAME = env("OTP_ISSUER_NAME", default="Central de Chamados")

# --- E-mail (alertas de login / 2FA) ---
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Central de Chamados <no-reply@example.com>")
