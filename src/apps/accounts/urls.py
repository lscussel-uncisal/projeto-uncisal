from django.contrib.auth import views as auth_views
from django.urls import path

from apps.accounts.views import (
    AccountPasswordChangeView,
    LoginReportView,
    PasswordResetDoneView,
    PasswordResetRequestView,
    ProfileUpdateView,
    ThrottledLoginView,
    TwoFactorConfirmSetupView,
    TwoFactorSetupView,
    TwoFactorVerifyView,
    UserCreateView,
    UserListView,
    user_toggle_active,
)

app_name = "accounts"

urlpatterns = [
    path("login/", ThrottledLoginView.as_view(), name="login"),
    path("login/2fa/", TwoFactorVerifyView.as_view(), name="two_factor_verify"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("conta/2fa/", TwoFactorSetupView.as_view(), name="two_factor_setup"),
    path("conta/2fa/confirmar/", TwoFactorConfirmSetupView.as_view(), name="two_factor_confirm"),
    path("conta/senha/", AccountPasswordChangeView.as_view(), name="password_change"),
    path("conta/perfil/", ProfileUpdateView.as_view(), name="profile"),
    path("recuperar-senha/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("recuperar-senha/enviado/", PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("usuarios/", UserListView.as_view(), name="user_list"),
    path("usuarios/novo/", UserCreateView.as_view(), name="user_create"),
    path("usuarios/<int:pk>/alternar-ativo/", user_toggle_active, name="user_toggle_active"),
    path("relatorio-login/", LoginReportView.as_view(), name="login_report"),
]
