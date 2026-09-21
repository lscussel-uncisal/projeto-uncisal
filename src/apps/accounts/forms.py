from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

from apps.accounts.services import TurnstileService, client_ip
from apps.core.forms import TailwindStyledFormMixin


class TurnstileAuthenticationForm(TailwindStyledFormMixin, AuthenticationForm):
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


class TwoFactorCodeForm(TailwindStyledFormMixin, forms.Form):
    """Formulario generico de codigo de 6 digitos — usado tanto no login (TOTP/e-mail)
    quanto na confirmacao de configuracao do segundo fator."""

    code = forms.CharField(
        label="Código de verificação",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(
            attrs={"inputmode": "numeric", "autocomplete": "one-time-code", "autofocus": True}
        ),
    )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not code.isdigit():
            raise ValidationError("O código deve conter só números.", code="invalid_code")
        return code


class TwoFactorMethodForm(forms.Form):
    """Escolha do metodo de segundo fator na tela de configuracao (auto-cadastro)."""

    METHOD_CHOICES = [
        ("totp", "Aplicativo autenticador (Google Authenticator, Authy, etc.)"),
        ("email", "Código por e-mail"),
    ]

    method = forms.ChoiceField(choices=METHOD_CHOICES, widget=forms.RadioSelect)
