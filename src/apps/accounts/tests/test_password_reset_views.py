from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.accounts.models import LoginAttempt, User
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
