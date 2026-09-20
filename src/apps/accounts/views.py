from django.conf import settings
from django.contrib.auth import views as auth_views
from django.core.exceptions import PermissionDenied

from apps.accounts.forms import TurnstileAuthenticationForm
from apps.accounts.models import LoginAttempt
from apps.accounts.services import LoginThrottleService, client_ip


class ThrottledLoginView(auth_views.LoginView):
    """LoginView padrao do Django + auditoria, bloqueio por forca bruta e Cloudflare Turnstile.

    TODO(proxima etapa): parede de 2FA (TOTP/e-mail) apos a senha.
    """

    template_name = "accounts/login.html"
    form_class = TurnstileAuthenticationForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["turnstile_enabled"] = settings.TURNSTILE_ENABLED
        context["turnstile_site_key"] = settings.TURNSTILE_SITE_KEY
        return context

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
