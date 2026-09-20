"""Utilitario interno de settings: nenhum modulo fora de config/settings deve importar isto."""

from django.core.exceptions import ImproperlyConfigured


def require(env, name: str) -> str:
    """Le uma variavel obrigatoria do ambiente; falha alto (nao cai em default inseguro)."""
    try:
        return env(name)
    except Exception as exc:
        raise ImproperlyConfigured(
            f"{name} nao definido no ambiente de producao. Configure via .env "
            "(fora do repositorio) ou GitHub Secrets."
        ) from exc
