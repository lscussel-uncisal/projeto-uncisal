import logging
from datetime import timedelta

import requests
from django.conf import settings
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
