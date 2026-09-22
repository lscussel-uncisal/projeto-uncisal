from django.contrib import admin
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseRedirect
from django.urls import include, path, reverse
from django.views.generic import RedirectView

from apps.core.views import healthz


class HomeRedirectView(RedirectView):
    """Raiz do site: manda pra lista de chamados. Se ninguem estiver logado, manda direto
    pro login com "?next=" ja apontando pra lista de chamados — em vez de um redirect duplo
    (raiz -> lista -> login?next=lista)."""

    def get(self, request, *args, **kwargs):
        tickets_list_url = reverse("tickets:list")
        if not request.user.is_authenticated:
            return redirect_to_login(tickets_list_url, login_url=reverse("accounts:login"))
        return HttpResponseRedirect(tickets_list_url)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
    path("", HomeRedirectView.as_view(), name="home"),
    path("", include("apps.accounts.urls")),
    path("chamados/", include("apps.tickets.urls")),
    path("backup/", include("apps.backup.urls")),
]
