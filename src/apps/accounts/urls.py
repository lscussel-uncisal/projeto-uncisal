from django.contrib.auth import views as auth_views
from django.urls import path

from apps.accounts.views import (
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
]
