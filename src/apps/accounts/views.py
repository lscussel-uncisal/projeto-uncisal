from datetime import datetime
from secrets import compare_digest

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import FormView

from apps.accounts.forms import (
    TurnstileAuthenticationForm,
    TwoFactorCodeForm,
    TwoFactorMethodForm,
)
from apps.accounts.models import LoginAttempt, TwoFactorDevice, TwoFactorMethod, User
from apps.accounts.services import LoginThrottleService, TwoFactorService, client_ip

# Chaves de sessao do CADASTRO de segundo fator (auto-servico, usuario ja autenticado) —
# namespace separado das chaves 2FA_* do login pendente acima, para nunca colidir caso o
# mesmo navegador tenha as duas coisas em andamento (pouco provavel, mas gratuito de evitar).
SESSION_2FA_SETUP_EMAIL_HASH = "2fa_setup_email_code_hash"
SESSION_2FA_SETUP_EMAIL_EXPIRES = "2fa_setup_email_code_expires"

# Chaves de sessao do login pendente de segundo fator. So existem entre a senha ser aceita
# e o codigo 2FA ser confirmado — nunca contem uma sessao autenticada (auth_login so roda
# depois do codigo certo, em TwoFactorVerifyView.form_valid).
SESSION_2FA_USER_ID = "2fa_user_id"
SESSION_2FA_METHOD = "2fa_method"
SESSION_2FA_NEXT_URL = "2fa_next_url"
SESSION_2FA_EMAIL_HASH = "2fa_email_code_hash"
SESSION_2FA_EMAIL_EXPIRES = "2fa_email_code_expires"


class ThrottledLoginView(auth_views.LoginView):
    """LoginView padrao do Django + auditoria, bloqueio por forca bruta e Cloudflare Turnstile.

    Se o usuario tiver um TwoFactorDevice confirmado, a senha certa NAO efetiva o login —
    so guarda a intencao na sessao e redireciona para TwoFactorVerifyView, que e quem
    chama auth_login() de verdade.
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

        device = getattr(user, "two_factor_device", None)
        if user.is_two_factor_enabled and device is not None and device.confirmed:
            email_hash = email_expires = None
            if device.method == TwoFactorMethod.EMAIL:
                code = TwoFactorService.generate_email_code()
                if not TwoFactorService.send_email_code(user=user, code=code):
                    form.add_error(
                        None,
                        "Não foi possível enviar o código de verificação por e-mail agora. "
                        "Tente novamente em instantes.",
                    )
                    return self.form_invalid(form)
                email_hash = TwoFactorService.hash_code(code)
                email_expires = (timezone.now() + TwoFactorService.EMAIL_CODE_TTL).isoformat()

            # So grava a sessao de login pendente depois do e-mail (se houver) ter saido de
            # verdade — senao um SMTP fora do ar deixaria lixo de sessao pra tras.
            self.request.session[SESSION_2FA_USER_ID] = user.pk
            self.request.session[SESSION_2FA_METHOD] = device.method
            self.request.session[SESSION_2FA_NEXT_URL] = self.get_success_url()
            if email_hash:
                self.request.session[SESSION_2FA_EMAIL_HASH] = email_hash
                self.request.session[SESSION_2FA_EMAIL_EXPIRES] = email_expires

            return redirect("accounts:two_factor_verify")

        return super().form_valid(form)

    def form_invalid(self, form):
        LoginThrottleService.record(
            result=LoginAttempt.Result.INVALID_CREDENTIALS,
            attempted_username=self.request.POST.get("username", ""),
            ip_address=client_ip(self.request),
        )
        return super().form_invalid(form)


class TwoFactorVerifyView(FormView):
    """Segunda etapa do login: confirma o codigo TOTP/e-mail e so entao autentica de fato."""

    template_name = "accounts/two_factor_verify.html"
    form_class = TwoFactorCodeForm

    def dispatch(self, request, *args, **kwargs):
        pending_user_id = request.session.get(SESSION_2FA_USER_ID)
        if not pending_user_id:
            return redirect("accounts:login")

        self.pending_user = User.objects.filter(pk=pending_user_id).first()
        if self.pending_user is None:
            self._clear_pending_session()
            return redirect("accounts:login")

        if LoginThrottleService.is_locked_out(
            attempted_username=self.pending_user.get_username(), ip_address=client_ip(request)
        ):
            raise PermissionDenied(
                "Muitas tentativas de verificação. Aguarde alguns minutos e tente novamente."
            )

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["method"] = self.request.session.get(SESSION_2FA_METHOD)
        return context

    def form_valid(self, form):
        code = form.cleaned_data["code"]
        method = self.request.session.get(SESSION_2FA_METHOD)

        if method == TwoFactorMethod.TOTP:
            correct = self._verify_totp_code(code)
        else:
            correct = self._verify_email_code(code)

        if not correct:
            LoginThrottleService.record(
                result=LoginAttempt.Result.INVALID_2FA,
                attempted_username=self.pending_user.get_username(),
                user=self.pending_user,
                ip_address=client_ip(self.request),
            )
            TwoFactorService.send_wrong_code_alert(user=self.pending_user)
            form.add_error("code", "Código incorreto.")
            return self.form_invalid(form)

        next_url = self.request.session.get(SESSION_2FA_NEXT_URL) or settings.LOGIN_REDIRECT_URL
        self._clear_pending_session()

        auth_login(self.request, self.pending_user)
        LoginThrottleService.record(
            result=LoginAttempt.Result.SUCCESS,
            attempted_username=self.pending_user.get_username(),
            user=self.pending_user,
            ip_address=client_ip(self.request),
        )
        return redirect(next_url)

    def _verify_totp_code(self, code: str) -> bool:
        device = getattr(self.pending_user, "two_factor_device", None)
        if device is None:
            return False
        return TwoFactorService.verify_totp(secret=device.totp_secret, code=code)

    def _verify_email_code(self, code: str) -> bool:
        expected_hash = self.request.session.get(SESSION_2FA_EMAIL_HASH)
        expires_raw = self.request.session.get(SESSION_2FA_EMAIL_EXPIRES)
        if not expected_hash or not expires_raw:
            return False
        if timezone.now() > datetime.fromisoformat(expires_raw):
            return False
        return compare_digest(TwoFactorService.hash_code(code), expected_hash)

    def _clear_pending_session(self):
        for key in (
            SESSION_2FA_USER_ID,
            SESSION_2FA_METHOD,
            SESSION_2FA_NEXT_URL,
            SESSION_2FA_EMAIL_HASH,
            SESSION_2FA_EMAIL_EXPIRES,
        ):
            self.request.session.pop(key, None)


class TwoFactorSetupView(LoginRequiredMixin, FormView):
    """Tela de auto-cadastro de 2FA: escolher metodo (ou desativar um ja confirmado).

    2FA e opcional por usuario (decisao explicita do usuario nesta conversa) — aqui so
    mostramos com clareza o risco real de nao ativar, sem forcar tecnicamente.
    """

    template_name = "accounts/two_factor_setup.html"
    form_class = TwoFactorMethodForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["device"] = TwoFactorDevice.objects.filter(user=self.request.user).first()
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get("action") == "disable":
            return self._disable()
        return super().post(request, *args, **kwargs)

    def _disable(self):
        user = self.request.user
        user.is_two_factor_enabled = False
        user.save(update_fields=["is_two_factor_enabled"])
        TwoFactorDevice.objects.filter(user=user).update(confirmed=False)
        messages.success(self.request, "Segundo fator desativado.")
        return redirect("accounts:two_factor_setup")

    def form_valid(self, form):
        method = form.cleaned_data["method"]
        user = self.request.user

        device, _created = TwoFactorDevice.objects.update_or_create(
            user=user, defaults={"method": method, "confirmed": False}
        )

        if method == TwoFactorMethod.TOTP:
            device.totp_secret = TwoFactorService.generate_totp_secret()
            device.save(update_fields=["totp_secret"])
        else:
            code = TwoFactorService.generate_email_code()
            if not TwoFactorService.send_email_code(user=user, code=code):
                form.add_error(
                    None,
                    "Não foi possível enviar o código de verificação por e-mail agora. "
                    "Tente novamente em instantes.",
                )
                return self.form_invalid(form)
            self.request.session[SESSION_2FA_SETUP_EMAIL_HASH] = TwoFactorService.hash_code(code)
            self.request.session[SESSION_2FA_SETUP_EMAIL_EXPIRES] = (
                timezone.now() + TwoFactorService.EMAIL_CODE_TTL
            ).isoformat()

        return redirect("accounts:two_factor_confirm")


class TwoFactorConfirmSetupView(LoginRequiredMixin, FormView):
    """Confirma o codigo do metodo escolhido em TwoFactorSetupView e ativa o 2FA de fato.

    Nao usa LoginThrottleService aqui de proposito: e uma acao de usuario ja autenticado
    (baixo risco comparado ao login), e reaproveitar o throttle por username bloquearia
    o LOGIN do usuario por causa de tentativas erradas na configuracao — efeitos colaterais
    diferentes, contadores diferentes.
    """

    template_name = "accounts/two_factor_confirm.html"
    form_class = TwoFactorCodeForm

    def dispatch(self, request, *args, **kwargs):
        self.device = TwoFactorDevice.objects.filter(user=request.user, confirmed=False).first()
        if self.device is None:
            return redirect("accounts:two_factor_setup")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["method"] = self.device.method
        if self.device.method == TwoFactorMethod.TOTP:
            uri = TwoFactorService.provisioning_uri(
                user=self.request.user, secret=self.device.totp_secret
            )
            context["qr_code_data_uri"] = TwoFactorService.qr_code_data_uri(uri)
        return context

    def form_valid(self, form):
        code = form.cleaned_data["code"]

        if self.device.method == TwoFactorMethod.TOTP:
            correct = TwoFactorService.verify_totp(secret=self.device.totp_secret, code=code)
        else:
            correct = self._verify_setup_email_code(code)

        if not correct:
            form.add_error("code", "Código incorreto.")
            return self.form_invalid(form)

        self.device.confirmed = True
        self.device.save(update_fields=["confirmed"])
        self.request.user.is_two_factor_enabled = True
        self.request.user.save(update_fields=["is_two_factor_enabled"])
        self.request.session.pop(SESSION_2FA_SETUP_EMAIL_HASH, None)
        self.request.session.pop(SESSION_2FA_SETUP_EMAIL_EXPIRES, None)
        messages.success(self.request, "Segundo fator configurado com sucesso.")
        return redirect("accounts:two_factor_setup")

    def _verify_setup_email_code(self, code: str) -> bool:
        expected_hash = self.request.session.get(SESSION_2FA_SETUP_EMAIL_HASH)
        expires_raw = self.request.session.get(SESSION_2FA_SETUP_EMAIL_EXPIRES)
        if not expected_hash or not expires_raw:
            return False
        if timezone.now() > datetime.fromisoformat(expires_raw):
            return False
        return compare_digest(TwoFactorService.hash_code(code), expected_hash)
