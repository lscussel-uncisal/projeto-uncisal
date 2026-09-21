import base64
import hashlib
import logging
import secrets
from datetime import timedelta
from io import BytesIO

import pyotp
import qrcode
import requests
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from apps.accounts.models import LoginAttempt, User

FAILED_RESULTS = (LoginAttempt.Result.INVALID_CREDENTIALS, LoginAttempt.Result.INVALID_2FA)

logger = logging.getLogger(__name__)


def client_ip(request) -> str | None:
    """IP real do visitante. Atras da Cloudflare, o Nginx repassa isto no header abaixo
    (ver docker/nginx/helpdesk.conf); sem Cloudflare (dev local), cai no IP da conexao."""
    return request.META.get("HTTP_CF_CONNECTING_IP") or request.META.get("REMOTE_ADDR")


class TurnstileService:
    """Verificacao server-side do Cloudflare Turnstile (siteverify API).

    So e chamada quando settings.TURNSTILE_ENABLED e True (ver ADR-009) — quem decide
    *se* verifica e o form/view, este servico so sabe *como* verificar um token.
    """

    VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    TIMEOUT_SECONDS = 5

    @classmethod
    def verify(cls, token: str, *, remote_ip: str | None = None) -> bool:
        if not token:
            return False

        payload = {"secret": settings.TURNSTILE_SECRET_KEY, "response": token}
        if remote_ip:
            payload["remoteip"] = remote_ip

        try:
            response = requests.post(cls.VERIFY_URL, data=payload, timeout=cls.TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException:
            # Falha alto pro visitante (nega acesso), mas nunca expõe o motivo real —
            # ver docs/security/owasp-mitigations.md, A10 (Mishandling of Exceptional Conditions).
            logger.error("Falha ao chamar a API do Cloudflare Turnstile", exc_info=True)
            return False

        return bool(response.json().get("success"))


class LoginThrottleService:
    """Contenção de força bruta no login/2FA (gerenciamento de risco, não só auditoria).

    Dois limites independentes, o mais restritivo decide:
    - por identificador digitado (username): protege uma conta especifica sendo atacada.
    - por IP de origem: protege contra um unico atacante testando varias contas
      (username spraying). Limite mais alto porque um IP pode representar varios
      usuarios legitimos atras do mesmo NAT/proxy.
    """

    WINDOW = timedelta(minutes=15)
    THRESHOLD_PER_USERNAME = 5
    THRESHOLD_PER_IP = 15

    @classmethod
    def record(
        cls,
        *,
        result: str,
        attempted_username: str = "",
        user: User | None = None,
        ip_address: str | None = None,
    ) -> LoginAttempt:
        return LoginAttempt.objects.create(
            user=user,
            attempted_username=attempted_username,
            result=result,
            ip_address=ip_address,
        )

    @classmethod
    def is_locked_out(cls, *, attempted_username: str, ip_address: str | None) -> bool:
        since = timezone.now() - cls.WINDOW
        recent_failures = LoginAttempt.objects.filter(
            created_at__gte=since, result__in=FAILED_RESULTS
        )

        by_username = recent_failures.filter(attempted_username__iexact=attempted_username).count()
        if by_username >= cls.THRESHOLD_PER_USERNAME:
            return True

        if ip_address:
            by_ip = recent_failures.filter(ip_address=ip_address).count()
            if by_ip >= cls.THRESHOLD_PER_IP:
                return True

        return False


class TwoFactorService:
    """Segundo fator de autenticacao: TOTP (app autenticador) ou codigo por e-mail.

    So sabe *como* gerar/verificar codigos e mandar e-mails — quem decide *quando* usar
    cada metodo e a view (ver ThrottledLoginView/TwoFactorVerifyView).
    """

    EMAIL_CODE_LENGTH = 6
    EMAIL_CODE_TTL = timedelta(minutes=10)

    @classmethod
    def generate_totp_secret(cls) -> str:
        return pyotp.random_base32()

    @classmethod
    def provisioning_uri(cls, *, user: User, secret: str) -> str:
        """URI otpauth:// para o QR code que o app autenticador escaneia."""
        return pyotp.TOTP(secret).provisioning_uri(
            name=user.email or user.get_username(), issuer_name=settings.OTP_ISSUER_NAME
        )

    @classmethod
    def qr_code_data_uri(cls, uri: str) -> str:
        """PNG do QR code do `provisioning_uri`, como data URI — sem precisar de uma
        view/endpoint separado so pra servir a imagem (o QR nunca precisa ser cacheado
        ou linkado, so aparece uma vez na tela de confirmacao do cadastro)."""
        image = qrcode.make(uri)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{encoded}"

    @classmethod
    def verify_totp(cls, *, secret: str, code: str) -> bool:
        if not secret or not code:
            return False
        # valid_window=1 tolera 1 passo de 30s de diferenca de relogio entre servidor e app.
        return pyotp.TOTP(secret).verify(code, valid_window=1)

    @classmethod
    def generate_email_code(cls) -> str:
        return f"{secrets.randbelow(10**cls.EMAIL_CODE_LENGTH):0{cls.EMAIL_CODE_LENGTH}d}"

    @classmethod
    def hash_code(cls, code: str) -> str:
        # Nao precisa ser um hash de senha (Argon2/bcrypt): o codigo e numerico, de vida
        # curta (EMAIL_CODE_TTL) e de uso unico — SHA-256 so evita guardar o valor puro
        # na sessao. Comparar sempre com secrets.compare_digest (ver TwoFactorVerifyView).
        return hashlib.sha256(code.encode()).hexdigest()

    @classmethod
    def send_email_code(cls, *, user: User, code: str) -> bool:
        """True se o e-mail foi enviado. False em falha do SMTP — quem chama decide o que
        fazer (ex.: nao redirecionar pra uma tela de "codigo enviado" que seria mentira).
        Nunca deixa a excecao subir: um SMTP fora do ar nao pode virar erro 500/stack trace
        pro usuario (ver docs/security/owasp-mitigations.md, A10)."""
        minutes = int(cls.EMAIL_CODE_TTL.total_seconds() // 60)
        try:
            send_mail(
                subject=f"{settings.OTP_ISSUER_NAME} - Código de verificação",
                message=(
                    f"Seu código de verificação é: {code}\n\n"
                    f"Ele expira em {minutes} minutos. Se você não tentou entrar na sua conta, "
                    "ignore este e-mail."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
        except OSError:
            logger.error("Falha ao enviar código de verificação por e-mail", exc_info=True)
            return False
        return True

    @classmethod
    def send_wrong_code_alert(cls, *, user: User) -> None:
        # Melhor esforço: se o SMTP falhar aqui, o codigo errado ja foi rejeitado
        # normalmente — um alerta que nao saiu nao pode virar erro 500 na resposta.
        try:
            send_mail(
                subject=f"{settings.OTP_ISSUER_NAME} - Código de verificação incorreto na sua conta",
                message=(
                    f"Detectamos uma tentativa de login na conta '{user.get_username()}' com um "
                    "código de verificação (2FA) incorreto.\n\n"
                    "Se foi você e só digitou o código errado, pode ignorar este e-mail.\n\n"
                    "Se não foi você, isso pode indicar que sua senha foi comprometida — "
                    "recomendamos trocar sua senha o quanto antes e verificar os dispositivos "
                    "conectados à sua conta."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )
        except OSError:
            logger.error("Falha ao enviar alerta de código 2FA incorreto", exc_info=True)
