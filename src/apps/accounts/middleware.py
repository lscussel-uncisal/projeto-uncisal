import time

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login

SESSION_AUTH_STARTED_AT = "auth_started_at"


class AbsoluteSessionTimeoutMiddleware:
    """Teto absoluto de duração da sessão, complementando o timeout por inatividade
    (SESSION_COOKIE_AGE + SESSION_SAVE_EVERY_REQUEST): sem ele, uma sessão usada sem parar
    nunca expiraria. Recomendação do OWASP Session Management Cheat Sheet (ADR-035)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = time.time()
            started_at = request.session.setdefault(SESSION_AUTH_STARTED_AT, now)
            if now - started_at > settings.SESSION_ABSOLUTE_TIMEOUT:
                logout(request)
                messages.info(request, "Sua sessão expirou. Entre novamente.")
                return redirect_to_login(request.get_full_path())
        return self.get_response(request)
