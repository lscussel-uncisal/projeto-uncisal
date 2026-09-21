from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.accounts.models import LoginAttempt, User
from apps.accounts.services import LoginThrottleService


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
