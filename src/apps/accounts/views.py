from django.contrib.auth import views as auth_views
from django.core.exceptions import PermissionDenied

from apps.accounts.models import LoginAttempt
from apps.accounts.services import LoginThrottleService


def client_ip(request) -> str | None:
    """IP real do visitante. Atras da Cloudflare, o Nginx repassa isto no header abaixo
    (ver docker/nginx/helpdesk.conf); sem Cloudflare (dev local), cai no IP da conexao."""
    return request.META.get("HTTP_CF_CONNECTING_IP") or request.META.get("REMOTE_ADDR")


class ThrottledLoginView(auth_views.LoginView):
    """LoginView padrao do Django + auditoria e bloqueio temporario por forca bruta.

    TODO(proxima etapa): Cloudflare Turnstile no form + parede de 2FA apos a senha.
    """

    template_name = "accounts/login.html"

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST":
            attempted_username = request.POST.get("username", "")
            if LoginThrottleService.is_locked_out(
                attempted_username=attempted_username, ip_address=client_ip(request)
            ):
                raise PermissionDenied(
                    "Muitas tentativas de login. Aguarde alguns minutos e tente novamente."
                )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        LoginThrottleService.record(
            result=LoginAttempt.Result.SUCCESS,
            attempted_username=user.get_username(),
            user=user,
            ip_address=client_ip(self.request),
        )
        return super().form_valid(form)

    def form_invalid(self, form):
        LoginThrottleService.record(
            result=LoginAttempt.Result.INVALID_CREDENTIALS,
            attempted_username=self.request.POST.get("username", ""),
            ip_address=client_ip(self.request),
        )
        return super().form_invalid(form)
