from django.contrib.auth import views as auth_views
from django.urls import path

from apps.accounts.views import (
    AccountPasswordChangeView,
    PasswordResetDoneView,
    PasswordResetRequestView,
    ThrottledLoginView,
    TwoFactorConfirmSetupView,
    TwoFactorSetupView,
    TwoFactorVerifyView,
)

app_name = "accounts"

urlpatterns = [
    path("login/", ThrottledLoginView.as_view(), name="login"),
    path("login/2fa/", TwoFactorVerifyView.as_view(), name="two_factor_verify"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("conta/2fa/", TwoFactorSetupView.as_view(), name="two_factor_setup"),
    path("conta/2fa/confirmar/", TwoFactorConfirmSetupView.as_view(), name="two_factor_confirm"),
    path("conta/senha/", AccountPasswordChangeView.as_view(), name="password_change"),
    path("recuperar-senha/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path("recuperar-senha/enviado/", PasswordResetDoneView.as_view(), name="password_reset_done"),
]
