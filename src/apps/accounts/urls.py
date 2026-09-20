from django.contrib.auth import views as auth_views
from django.urls import path

from apps.accounts.views import ThrottledLoginView

app_name = "accounts"

urlpatterns = [
    # TODO(proxima etapa): adicionar Cloudflare Turnstile + parede de 2FA na ThrottledLoginView.
    path("login/", ThrottledLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
