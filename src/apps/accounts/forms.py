from django import forms
from django.conf import settings
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import PasswordChangeForm as DjangoPasswordChangeForm
from django.core.exceptions import ValidationError

from apps.accounts.models import Role, User
from apps.accounts.services import TurnstileService, UserAdminService, client_ip
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


class UserCreateForm(TailwindStyledFormMixin, forms.ModelForm):
    """Criação de usuário por um admin ou super-admin. Nasce com set_unusable_password() —
    nunca uma senha definida aqui (nem gerada nem digitada por quem cria): o próprio usuário
    define a senha via 'Esqueci minha senha' (ver AccountNotificationService.send_welcome_email),
    reaproveitando o fluxo já existente em vez de duplicar geração/transmissão de senha.

    Recebe `actor` (quem está criando) pra restringir os papéis que podem ser atribuídos —
    tanto escondendo do dropdown quanto rejeitando em clean_role, pra nunca depender só da
    UI: um admin nunca pode criar super-admin, nem forjando o POST diretamente."""

    email = forms.EmailField(label="E-mail (também será o nome de usuário para login)")

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "role"]
        labels = {"first_name": "Nome", "last_name": "Sobrenome", "role": "Papel"}

    def __init__(self, *args, actor=None, **kwargs):
        self.actor = actor
        super().__init__(*args, **kwargs)
        allowed = UserAdminService.creatable_roles(actor) if actor else set()
        self.fields["role"].choices = [
            (value, label) for value, label in Role.choices if value in allowed
        ]

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(username__iexact=email).exists():
            raise ValidationError("Já existe uma conta com esse e-mail.", code="duplicate_email")
        return email

    def clean_role(self):
        role = self.cleaned_data.get("role")
        allowed = UserAdminService.creatable_roles(self.actor) if self.actor else set()
        if role not in allowed:
            raise ValidationError(
                "Você não tem permissão para atribuir esse papel.", code="role_not_allowed"
            )
        return role

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.set_unusable_password()
        if commit:
            user.save()
        return user


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
