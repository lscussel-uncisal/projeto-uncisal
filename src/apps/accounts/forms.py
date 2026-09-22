from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.core.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounts.services import TurnstileService, client_ip
from apps.core.forms import TailwindStyledFormMixin


class TurnstileProtectedFormMixin:
    """Checa o Cloudflare Turnstile ANTES do resto da validacao do formulario (falha rapido
    em trafego automatizado, sem gastar autenticacao/consulta ao banco nele). So verifica de
    fato quando settings.TURNSTILE_ENABLED (ver ADR-009) — em dev, sem chave configurada, o
    formulario se comporta normalmente. O Form precisa receber `request` no __init__ (ver
    TurnstileAuthenticationForm — AuthenticationForm já faz isso; PasswordResetRequestForm
    aceita explicitamente).
    """

    def clean(self):
        if settings.TURNSTILE_ENABLED:
            token = self.data.get("cf-turnstile-response", "")
            remote_ip = client_ip(self.request) if getattr(self, "request", None) else None
            if not TurnstileService.verify(token, remote_ip=remote_ip):
                raise ValidationError(
                    "Verificação de segurança falhou. Recarregue a página e tente novamente.",
                    code="turnstile_invalid",
                )
        return super().clean()


class TurnstileAuthenticationForm(
    TurnstileProtectedFormMixin, TailwindStyledFormMixin, AuthenticationForm
):
    """AuthenticationForm padrao do Django + verificacao do Cloudflare Turnstile — checada
    ANTES das credenciais, sem revelar se a senha estaria certa ou nao."""


class PasswordResetRequestForm(TurnstileProtectedFormMixin, TailwindStyledFormMixin, forms.Form):
    """Pedido de recuperação de senha: só o e-mail + Turnstile. A view NUNCA revela se o
    e-mail existe ou não — a resposta é sempre a mesma, exista conta ou não (ver ADR)."""

    email = forms.EmailField(label="E-mail")

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)


class PasswordChangeForm(TailwindStyledFormMixin, DjangoPasswordChangeForm):
    """PasswordChangeForm padrao do Django (exige a senha atual) + estilo Tailwind."""


class ProfileForm(TailwindStyledFormMixin, forms.ModelForm):
    """Autoatendimento: o próprio usuário edita nome/sobrenome (User.display_name). Nunca
    inclui e-mail/username aqui — troca de e-mail de login é operação sensível o bastante
    pra não caber num form de "editar meu nome" (fora do escopo atual)."""

    class Meta:
        model = User
        fields = ["first_name", "last_name"]
        labels = {"first_name": "Nome", "last_name": "Sobrenome"}


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
