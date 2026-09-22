from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.accounts.models import LoginAttempt, TwoFactorDevice, TwoFactorMethod, User
from apps.accounts.services import PasswordResetThrottleService


@pytest.mark.django_db
class TestPasswordResetRequestView:
    def _post(self, client, email):
        with patch("apps.accounts.forms.TurnstileService.verify", return_value=True):
            return client.post(
                reverse("accounts:password_reset_request"),
                {"email": email, "cf-turnstile-response": "token"},
            )

    def test_existing_email_gets_a_temp_password_and_generic_response(self, client, mailoutbox):
        user = User.objects.create_user(
            username="joao", password="senha-antiga-123", email="joao@example.com"
        )

        response = self._post(client, "joao@example.com")

        assert response.status_code == 302
        assert response.url == reverse("accounts:password_reset_done")
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ["joao@example.com"]
        user.refresh_from_db()
        assert not user.check_password("senha-antiga-123")

    def test_nonexistent_email_gets_the_exact_same_response(self, client, mailoutbox):
        response = self._post(client, "ninguem@example.com")

        assert response.status_code == 302
        assert response.url == reverse("accounts:password_reset_done")
        assert len(mailoutbox) == 0

    def test_inactive_user_email_gets_the_exact_same_response_and_no_email(
        self, client, mailoutbox
    ):
        User.objects.create_user(
            username="joao",
            password="senha-123",
            email="joao@example.com",
            is_active=False,
        )

        response = self._post(client, "joao@example.com")

        assert response.status_code == 302
        assert response.url == reverse("accounts:password_reset_done")
        assert len(mailoutbox) == 0

    def test_records_the_request_for_throttling_regardless_of_match(self, client):
        self._post(client, "ninguem@example.com")

        attempt = LoginAttempt.objects.get()
        assert attempt.result == LoginAttempt.Result.PASSWORD_RESET_REQUESTED
        assert attempt.attempted_username == "ninguem@example.com"

    def test_throttled_requests_get_the_same_response_and_send_nothing(self, client, mailoutbox):
        user = User.objects.create_user(
            username="joao", password="senha-123", email="joao@example.com"
        )
        for _ in range(PasswordResetThrottleService.THRESHOLD_PER_EMAIL):
            PasswordResetThrottleService.record(email="joao@example.com", ip_address="1.2.3.4")

        response = self._post(client, "joao@example.com")

        assert response.status_code == 302
        assert response.url == reverse("accounts:password_reset_done")
        assert len(mailoutbox) == 0
        user.refresh_from_db()
        assert user.check_password("senha-123")

    def test_does_not_change_password_when_smtp_fails(self, client):
        user = User.objects.create_user(
            username="joao", password="senha-antiga-123", email="joao@example.com"
        )

        with patch(
            "apps.accounts.views.AccountNotificationService.send_temp_password",
            return_value=False,
        ):
            response = self._post(client, "joao@example.com")

        assert response.status_code == 302
        user.refresh_from_db()
        assert user.check_password("senha-antiga-123")


@pytest.mark.django_db
class TestPasswordResetDoesNotDisturbTwoFactor:
    """A recuperação de senha nunca deve desligar nem contornar um 2FA já configurado — só
    troca a senha (`user.set_password`), nunca `is_two_factor_enabled`/`TwoFactorDevice`.
    A prova real é ponta a ponta: pedir a senha nova, tentar logar só com ela, e confirmar
    que o 2FA ainda barra o acesso até o código certo ser digitado."""

    def _post_reset(self, client, email):
        with patch("apps.accounts.forms.TurnstileService.verify", return_value=True):
            return client.post(
                reverse("accounts:password_reset_request"),
                {"email": email, "cf-turnstile-response": "token"},
            )

    def test_temp_password_alone_does_not_bypass_totp_2fa(self, client, mailoutbox):
        user = User.objects.create_user(
            username="joao@example.com",
            password="senha-antiga-123",
            email="joao@example.com",
            is_two_factor_enabled=True,
        )
        device = TwoFactorDevice.objects.create(
            user=user, method=TwoFactorMethod.TOTP, confirmed=True
        )
        device.totp_secret = "JBSWY3DPEHPK3PXP"
        device.save(update_fields=["totp_secret"])

        self._post_reset(client, "joao@example.com")
        temp_password = mailoutbox[0].body.split("é: ")[1].split("\n")[0]

        user.refresh_from_db()
        assert user.is_two_factor_enabled is True
        assert user.two_factor_device.confirmed is True

        with patch("apps.accounts.forms.TurnstileService.verify", return_value=True):
            response = client.post(
                reverse("accounts:login"),
                {"username": "joao@example.com", "password": temp_password},
            )

        # Senha certa, mas login ainda NAO efetivado — precisa passar pelo 2FA primeiro.
        assert response.status_code == 302
        assert response.url == reverse("accounts:two_factor_verify")
        assert "_auth_user_id" not in client.session

    def test_temp_password_alone_does_not_bypass_email_2fa(self, client, mailoutbox):
        user = User.objects.create_user(
            username="joao@example.com",
            password="senha-antiga-123",
            email="joao@example.com",
            is_two_factor_enabled=True,
        )
        TwoFactorDevice.objects.create(user=user, method=TwoFactorMethod.EMAIL, confirmed=True)

        self._post_reset(client, "joao@example.com")
        temp_password = mailoutbox[0].body.split("é: ")[1].split("\n")[0]

        with patch("apps.accounts.forms.TurnstileService.verify", return_value=True):
            response = client.post(
                reverse("accounts:login"),
                {"username": "joao@example.com", "password": temp_password},
            )

        assert response.status_code == 302
        assert response.url == reverse("accounts:two_factor_verify")
        assert "_auth_user_id" not in client.session

        # E o codigo do 2FA (enviado num segundo e-mail) ainda funciona normalmente.
        code_email = mailoutbox[1]
        sent_code = code_email.body.split("é: ")[1].split("\n")[0]
        response = client.post(reverse("accounts:two_factor_verify"), {"code": sent_code})

        assert response.status_code == 302
        assert "_auth_user_id" in client.session
