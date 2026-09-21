from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from apps.accounts.services import TurnstileService, client_ip


class TurnstileAuthenticationForm(AuthenticationForm):
    """AuthenticationForm padrao do Django + verificacao do Cloudflare Turnstile.

    Turnstile e checado ANTES das credenciais (falha rapido em trafego automatizado,
    sem gastar um authenticate() nele, e nao revela se a senha estaria certa ou nao).
    So verifica de fato quando settings.TURNSTILE_ENABLED (ver ADR-009) — em dev, sem
    chave configurada, o formulario se comporta como um AuthenticationForm normal.
    """

    def clean(self):
        if settings.TURNSTILE_ENABLED:
            token = self.data.get("cf-turnstile-response", "")
            remote_ip = client_ip(self.request) if self.request else None
            if not TurnstileService.verify(token, remote_ip=remote_ip):
                raise ValidationError(
                    "Verificação de segurança falhou. Recarregue a página e tente novamente.",
                    code="turnstile_invalid",
                )
        return super().clean()
