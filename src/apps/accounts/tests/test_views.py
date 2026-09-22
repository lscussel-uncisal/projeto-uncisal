from unittest.mock import patch

import pyotp
import pytest
from django.urls import reverse

from apps.accounts.models import LoginAttempt, TwoFactorDevice, TwoFactorMethod, User
from apps.accounts.services import LoginThrottleService
from apps.accounts.views import SESSION_2FA_USER_ID


@pytest.mark.django_db
class TestThrottledLoginView:
    def test_successful_login_records_success_attempt(self, client):
        User.objects.create_user(username="joao", password="senha-forte-123")

        with patch("apps.accounts.forms.TurnstileService.verify", return_value=True):
            response = client.post(
                reverse("accounts:login"),
                {
                    "username": "joao",
                    "password": "senha-forte-123",
                    "cf-turnstile-response": "token",
                },
            )

        assert response.status_code == 302
        attempt = LoginAttempt.objects.get()
        assert attempt.result == LoginAttempt.Result.SUCCESS
        assert attempt.user.username == "joao"

    def test_successful_login_sends_a_notification_email(self, client, mailoutbox):
        User.objects.create_user(
            username="joao", password="senha-forte-123", email="joao@example.com"
        )

        with patch("apps.accounts.forms.TurnstileService.verify", return_value=True):
            client.post(
                reverse("accounts:login"),
                {
                    "username": "joao",
                    "password": "senha-forte-123",
                    "cf-turnstile-response": "token",
                },
            )

        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ["joao@example.com"]
        assert "login" in mailoutbox[0].subject.lower()

    def test_login_blocked_without_a_valid_turnstile_token(self, client):
        User.objects.create_user(username="joao", password="senha-forte-123")

        with patch(
            "apps.accounts.forms.TurnstileService.verify", return_value=False
        ) as mock_verify:
            response = client.post(
                reverse("accounts:login"), {"username": "joao", "password": "senha-forte-123"}
            )

        assert response.status_code == 200
        mock_verify.assert_called_once()
        assert "_auth_user_id" not in client.session

    def test_failed_login_records_invalid_credentials_attempt(self, client):
        User.objects.create_user(username="joao", password="senha-forte-123")

        response = client.post(
            reverse("accounts:login"), {"username": "joao", "password": "senha-errada"}
        )

        assert response.status_code == 200
        attempt = LoginAttempt.objects.get()
        assert attempt.result == LoginAttempt.Result.INVALID_CREDENTIALS
        assert attempt.attempted_username == "joao"
        assert attempt.user is None

    def test_unknown_username_is_still_audited(self, client):
        client.post(reverse("accounts:login"), {"username": "nao-existe", "password": "qualquer"})

        attempt = LoginAttempt.objects.get()
        assert attempt.attempted_username == "nao-existe"
        assert attempt.user is None

    def test_blocks_login_after_threshold_failed_attempts(self, client):
        User.objects.create_user(username="joao", password="senha-forte-123")
        for _ in range(LoginThrottleService.THRESHOLD_PER_USERNAME):
            client.post(reverse("accounts:login"), {"username": "joao", "password": "senha-errada"})

        response = client.post(
            reverse("accounts:login"), {"username": "joao", "password": "senha-forte-123"}
        )

        assert response.status_code == 403

    def test_user_with_confirmed_2fa_is_redirected_to_verify_instead_of_logged_in(self, client):
        user = User.objects.create_user(
            username="joao", password="senha-forte-123", is_two_factor_enabled=True
        )
        TwoFactorDevice.objects.create(
            user=user, method=TwoFactorMethod.TOTP, totp_secret="ABCDEFGHIJKLMNOP", confirmed=True
        )

        with patch("apps.accounts.forms.TurnstileService.verify", return_value=True):
            response = client.post(
                reverse("accounts:login"), {"username": "joao", "password": "senha-forte-123"}
            )

        assert response.status_code == 302
        assert response.url == reverse("accounts:two_factor_verify")
        assert "_auth_user_id" not in client.session

    def test_user_without_confirmed_2fa_device_logs_in_directly(self, client):
        user = User.objects.create_user(
            username="joao", password="senha-forte-123", is_two_factor_enabled=True
        )
        # is_two_factor_enabled=True mas sem device confirmado (ex.: ligou a flag mas nao
        # terminou o cadastro) nao deve travar o usuario para sempre fora da conta.
        TwoFactorDevice.objects.create(
            user=user, method=TwoFactorMethod.TOTP, totp_secret="ABCDEFGHIJKLMNOP", confirmed=False
        )

        with patch("apps.accounts.forms.TurnstileService.verify", return_value=True):
            response = client.post(
                reverse("accounts:login"), {"username": "joao", "password": "senha-forte-123"}
            )

        assert response.status_code == 302
        assert "_auth_user_id" in client.session


@pytest.mark.django_db
class TestTwoFactorVerifyView:
    def _login_until_2fa_pending(self, client, user, password="senha-forte-123"):
        with patch("apps.accounts.forms.TurnstileService.verify", return_value=True):
            client.post(
                reverse("accounts:login"), {"username": user.username, "password": password}
            )

    def test_cannot_access_verify_page_without_a_pending_login(self, client):
        response = client.get(reverse("accounts:two_factor_verify"))

        assert response.status_code == 302
        assert response.url == reverse("accounts:login")

    def test_correct_totp_code_logs_the_user_in(self, client, mailoutbox):
        secret = pyotp.random_base32()
        user = User.objects.create_user(
            username="joao",
            password="senha-forte-123",
            email="joao@example.com",
            is_two_factor_enabled=True,
        )
        TwoFactorDevice.objects.create(
            user=user, method=TwoFactorMethod.TOTP, totp_secret=secret, confirmed=True
        )
        self._login_until_2fa_pending(client, user)

        response = client.post(
            reverse("accounts:two_factor_verify"), {"code": pyotp.TOTP(secret).now()}
        )

        assert response.status_code == 302
        assert "_auth_user_id" in client.session
        assert len(mailoutbox) == 1
        assert "login" in mailoutbox[0].subject.lower()

    def test_wrong_totp_code_does_not_log_in_and_sends_alert_email(self, client, mailoutbox):
        secret = pyotp.random_base32()
        user = User.objects.create_user(
            username="joao",
            password="senha-forte-123",
            email="joao@example.com",
            is_two_factor_enabled=True,
        )
        TwoFactorDevice.objects.create(
            user=user, method=TwoFactorMethod.TOTP, totp_secret=secret, confirmed=True
        )
        self._login_until_2fa_pending(client, user)

        response = client.post(reverse("accounts:two_factor_verify"), {"code": "000000"})

        assert response.status_code == 200
        assert "_auth_user_id" not in client.session
        attempt = LoginAttempt.objects.filter(result=LoginAttempt.Result.INVALID_2FA).get()
        assert attempt.user == user
        assert len(mailoutbox) == 1
        assert "senha" in mailoutbox[0].body.lower()

    def test_correct_email_code_logs_the_user_in(self, client, mailoutbox):
        user = User.objects.create_user(
            username="joao",
            password="senha-forte-123",
            email="joao@example.com",
            is_two_factor_enabled=True,
        )
        TwoFactorDevice.objects.create(user=user, method=TwoFactorMethod.EMAIL, confirmed=True)
        self._login_until_2fa_pending(client, user)
        sent_code = mailoutbox[0].body.split("é: ")[1].split("\n")[0]

        response = client.post(reverse("accounts:two_factor_verify"), {"code": sent_code})

        assert response.status_code == 302
        assert "_auth_user_id" in client.session
        assert len(mailoutbox) == 2  # [0] codigo de verificacao, [1] notificacao de login
        assert "login" in mailoutbox[1].subject.lower()

    def test_wrong_email_code_does_not_log_in(self, client, mailoutbox):
        user = User.objects.create_user(
            username="joao",
            password="senha-forte-123",
            email="joao@example.com",
            is_two_factor_enabled=True,
        )
        TwoFactorDevice.objects.create(user=user, method=TwoFactorMethod.EMAIL, confirmed=True)
        self._login_until_2fa_pending(client, user)

        response = client.post(reverse("accounts:two_factor_verify"), {"code": "000000"})

        assert response.status_code == 200
        assert "_auth_user_id" not in client.session

    def test_locks_out_after_threshold_wrong_2fa_attempts(self, client):
        secret = pyotp.random_base32()
        user = User.objects.create_user(
            username="joao",
            password="senha-forte-123",
            email="joao@example.com",
            is_two_factor_enabled=True,
        )
        TwoFactorDevice.objects.create(
            user=user, method=TwoFactorMethod.TOTP, totp_secret=secret, confirmed=True
        )
        self._login_until_2fa_pending(client, user)
        for _ in range(LoginThrottleService.THRESHOLD_PER_USERNAME):
            client.post(reverse("accounts:two_factor_verify"), {"code": "000000"})

        response = client.get(reverse("accounts:two_factor_verify"))

        assert response.status_code == 403

    def test_smtp_failure_shows_error_instead_of_pretending_the_code_was_sent(self, client):
        user = User.objects.create_user(
            username="joao",
            password="senha-forte-123",
            email="joao@example.com",
            is_two_factor_enabled=True,
        )
        TwoFactorDevice.objects.create(user=user, method=TwoFactorMethod.EMAIL, confirmed=True)

        with (
            patch("apps.accounts.forms.TurnstileService.verify", return_value=True),
            patch("apps.accounts.views.TwoFactorService.send_email_code", return_value=False),
        ):
            response = client.post(
                reverse("accounts:login"), {"username": "joao", "password": "senha-forte-123"}
            )

        assert response.status_code == 200
        assert SESSION_2FA_USER_ID not in client.session
        assert b"e-mail" in response.content
