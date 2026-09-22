from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.core.fields import EncryptedCharField
from apps.core.models import TimeStampedModel


class Role(models.TextChoices):
    ADMIN = "admin", "Administrador"
    SUPPORT = "support", "Suporte"
    USER = "user", "Usuário"


class User(AbstractUser):
    """Usuário customizado: adiciona papel (RBAC) e flag de 2FA ao modelo padrão do Django."""

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.USER)
    is_two_factor_enabled = models.BooleanField(
        default=False,
        help_text=(
            "Sem 2FA, uma senha vazada ou reaproveitada de outro site já é suficiente para "
            "tomar esta conta — não é um risco hipotético, é o vetor de invasão mais comum. "
            "Esta flag só reflete se o usuário terminou a configuração; ative em "
            "'Segurança da conta' após o primeiro login (aplicativo autenticador ou e-mail)."
        ),
    )

    @property
    def is_admin_role(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_support_role(self) -> bool:
        return self.role == Role.SUPPORT

    @property
    def display_name(self) -> str:
        """Nome amigável pra exibir a outros usuários (ex.: campo 'Responsável' de um chamado).

        Nunca retorna o e-mail: username == e-mail neste projeto, e e-mail é credencial de
        login — expor pra qualquer usuário autenticado facilita phishing/engenharia social
        direcionada à equipe de suporte. Sem nome/sobrenome cadastrado, cai pro identificador
        local do e-mail (antes do @), nunca o endereço inteiro.
        """
        full_name = self.get_full_name()
        return full_name if full_name else self.username.split("@")[0]

    def __str__(self) -> str:
        return self.display_name


class TwoFactorMethod(models.TextChoices):
    TOTP = "totp", "Aplicativo autenticador"
    EMAIL = "email", "E-mail"


class TwoFactorDevice(TimeStampedModel):
    """Configuração de segundo fator de um usuário (um dispositivo/método ativo por vez)."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="two_factor_device")
    method = models.CharField(max_length=10, choices=TwoFactorMethod.choices)
    # Criptografado em repouso (ver apps/core/fields.py) — max_length maior por causa
    # do overhead do token Fernet sobre o segredo TOTP original (~32 chars em base32).
    totp_secret = EncryptedCharField(max_length=255, blank=True)
    confirmed = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"{self.user} ({self.get_method_display()})"


class LoginAttempt(TimeStampedModel):
    """Auditoria de tentativas de autenticação.

    Base para: (1) alerta por e-mail em 2FA incorreto, (2) bloqueio temporário por força
    bruta (`LoginThrottleService`). `user` é opcional de propósito: um usuário inexistente
    (ataque de enumeração) também precisa ficar auditado, então guardamos sempre o texto
    digitado em `attempted_username`, e o FK só quando o usuário realmente existe.
    """

    class Result(models.TextChoices):
        SUCCESS = "success", "Sucesso"
        INVALID_CREDENTIALS = "invalid_credentials", "Credenciais inválidas"
        INVALID_2FA = "invalid_2fa", "Código 2FA inválido"
        PASSWORD_RESET_REQUESTED = "password_reset_requested", "Recuperação de senha solicitada"

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="login_attempts"
    )
    attempted_username = models.CharField(max_length=150, blank=True)
    result = models.CharField(max_length=30, choices=Result.choices)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["attempted_username", "created_at"]),
            models.Index(fields=["ip_address", "created_at"]),
        ]

    def __str__(self) -> str:
        who = self.user or self.attempted_username or "desconhecido"
        return f"{who} - {self.result} - {self.created_at:%Y-%m-%d %H:%M}"
