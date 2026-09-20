from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import LoginAttempt, User

FAILED_RESULTS = (LoginAttempt.Result.INVALID_CREDENTIALS, LoginAttempt.Result.INVALID_2FA)


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
