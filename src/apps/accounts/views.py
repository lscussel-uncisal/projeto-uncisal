from datetime import datetime
from secrets import compare_digest

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, FormView, ListView, TemplateView, UpdateView

from apps.accounts.forms import (
    PasswordChangeForm,
    PasswordResetRequestForm,
    ProfileForm,
    TurnstileAuthenticationForm,
    TwoFactorCodeForm,
    TwoFactorMethodForm,
    UserCreateForm,
)
from apps.accounts.models import LoginAttempt, Role, TwoFactorDevice, TwoFactorMethod, User
from apps.accounts.permissions import role_required
from apps.accounts.services import (
    AccountNotificationService,
    LoginThrottleService,
    PasswordResetThrottleService,
    TwoFactorService,
    UserAdminService,
    client_ip,
)

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

        AccountNotificationService.send_login_notification(
            user=user, ip_address=client_ip(self.request)
        )
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
        AccountNotificationService.send_login_notification(
            user=self.pending_user, ip_address=client_ip(self.request)
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


class PasswordResetRequestView(FormView):
    """Pedido de recuperação de senha: só e-mail + Turnstile.

    A resposta é SEMPRE a mesma — exista conta com esse e-mail ou não, esteja throttled
    ou não — nunca revela nada sobre a existência da conta (ver ADR em
    docs/architecture/decisions.md). Por isso não há form_invalid especial nem branch de
    "e-mail não encontrado": tudo cai no mesmo redirect de sucesso.
    """

    template_name = "accounts/password_reset_request.html"
    form_class = PasswordResetRequestForm
    success_url = reverse_lazy("accounts:password_reset_done")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["turnstile_enabled"] = settings.TURNSTILE_ENABLED
        context["turnstile_site_key"] = settings.TURNSTILE_SITE_KEY
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        email = form.cleaned_data["email"]
        ip = client_ip(self.request)

        if not PasswordResetThrottleService.is_locked_out(email=email, ip_address=ip):
            PasswordResetThrottleService.record(email=email, ip_address=ip)
            user = User.objects.filter(email__iexact=email, is_active=True).first()
            if user is not None:
                temp_password = AccountNotificationService.generate_temp_password()
                # So efetiva a senha nova DEPOIS de confirmar que o e-mail saiu — senao um
                # SMTP fora do ar trocaria a senha real sem o usuario nunca saber qual e a nova.
                if AccountNotificationService.send_temp_password(
                    user=user, temp_password=temp_password
                ):
                    user.set_password(temp_password)
                    user.save(update_fields=["password"])

        return super().form_valid(form)


class PasswordResetDoneView(TemplateView):
    template_name = "accounts/password_reset_done.html"


class AccountPasswordChangeView(auth_views.PasswordChangeView):
    """Troca de senha self-service — exige a senha atual (Django cuida disso). Acessível
    pelo usuário já logado, sem precisar do admin."""

    template_name = "accounts/password_change.html"
    form_class = PasswordChangeForm
    success_url = reverse_lazy("tickets:list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Senha alterada com sucesso.")
        return response


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Autoatendimento: o usuário edita o próprio nome. `get_object` sempre retorna
    `request.user`, ignorando qualquer id/pk que venha no POST — não há como um usuário
    editar o nome de outra pessoa via dado forjado no formulário."""

    model = User
    form_class = ProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("tickets:list")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Nome atualizado com sucesso.")
        return response


@method_decorator(role_required(Role.ADMIN, Role.SUPER_ADMIN), name="dispatch")
class UserListView(ListView):
    """Gestão de usuários (ativar/desativar). Protegida no servidor por role_required —
    quem não for admin/super-admin recebe 403 mesmo sabendo a URL, não é só um link
    escondido. Admin comum nunca vê conta super-admin (ver UserAdminService.visible_to)."""

    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"

    def get_queryset(self):
        return UserAdminService.visible_to(self.request.user)


@method_decorator(role_required(Role.ADMIN, Role.SUPER_ADMIN), name="dispatch")
class UserCreateView(CreateView):
    """Criação de usuário por um admin ou super-admin — protegida no servidor pelo mesmo
    role_required de UserListView. Nunca define senha aqui (ver UserCreateForm.save). Papel
    atribuível é restringido por quem está criando (ver UserCreateForm/UserAdminService) —
    admin nunca cria super-admin, nem forjando o POST."""

    model = User
    form_class = UserCreateForm
    template_name = "accounts/user_form.html"
    success_url = reverse_lazy("accounts:user_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["actor"] = self.request.user
        return kwargs

    def form_valid(self, form):
        response = super().form_valid(form)
        AccountNotificationService.send_welcome_email(user=self.object)
        messages.success(self.request, f"{self.object.display_name} foi cadastrado(a).")
        return response


@method_decorator(role_required(Role.ADMIN, Role.SUPER_ADMIN), name="dispatch")
class LoginReportView(ListView):
    """Auditoria de tentativas de login (sucesso, falha, 2FA incorreto, recuperação de senha
    solicitada) — mesma proteção server-side das outras telas de administração."""

    model = LoginAttempt
    template_name = "accounts/login_report.html"
    context_object_name = "attempts"
    paginate_by = 30

    def get_queryset(self):
        queryset = LoginAttempt.objects.select_related("user").order_by("-created_at")

        result = self.request.GET.get("result")
        if result in LoginAttempt.Result.values:
            queryset = queryset.filter(result=result)

        date_from = self.request.GET.get("date_from")
        if date_from:
            queryset = queryset.filter(created_at__date__gte=date_from)

        date_to = self.request.GET.get("date_to")
        if date_to:
            queryset = queryset.filter(created_at__date__lte=date_to)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["result_choices"] = LoginAttempt.Result.choices
        context["selected_result"] = self.request.GET.get("result", "")
        context["date_from"] = self.request.GET.get("date_from", "")
        context["date_to"] = self.request.GET.get("date_to", "")
        return context


@role_required(Role.ADMIN, Role.SUPER_ADMIN)
@require_POST
def user_toggle_active(request, pk):
    """Ativa/desativa um usuário. Mesma proteção server-side de UserListView — GET não é
    aceito de propósito (ação com efeito colateral não pode ser um link/GET, CSRF-safe).
    Busca em UserAdminService.visible_to: um admin tentando atingir uma conta super-admin
    via URL forjada recebe 404 (não 403) — nem confirma que a conta existe."""
    target = get_object_or_404(UserAdminService.visible_to(request.user), pk=pk)
    try:
        UserAdminService.toggle_active(actor=request.user, target=target)
    except ValueError:
        return HttpResponseBadRequest("Não é possível ativar/desativar a própria conta.")

    status = "ativado" if target.is_active else "desativado"
    messages.success(request, f"{target.display_name} foi {status}.")
    return redirect("accounts:user_list")
