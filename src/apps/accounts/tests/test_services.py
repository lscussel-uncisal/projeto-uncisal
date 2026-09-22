import pytest

from apps.accounts.models import LoginAttempt, User
from apps.accounts.services import LoginThrottleService, PasswordResetThrottleService


@pytest.mark.django_db
class TestLoginThrottleService:
    def test_not_locked_out_with_no_attempts(self):
        assert (
            LoginThrottleService.is_locked_out(attempted_username="ninguem", ip_address="1.2.3.4")
            is False
        )

    def test_locks_out_after_threshold_failures_for_same_username(self):
        for _ in range(LoginThrottleService.THRESHOLD_PER_USERNAME):
            LoginThrottleService.record(
                result=LoginAttempt.Result.INVALID_CREDENTIALS,
                attempted_username="vitima",
                ip_address="1.2.3.4",
            )

        assert (
            LoginThrottleService.is_locked_out(attempted_username="vitima", ip_address="9.9.9.9")
            is True
        )

    def test_does_not_lock_out_a_different_username_from_same_ip_below_ip_threshold(self):
        for _ in range(LoginThrottleService.THRESHOLD_PER_USERNAME):
            LoginThrottleService.record(
                result=LoginAttempt.Result.INVALID_CREDENTIALS,
                attempted_username="outra-conta",
                ip_address="1.2.3.4",
            )

        assert (
            LoginThrottleService.is_locked_out(attempted_username="vitima", ip_address="8.8.8.8")
            is False
        )

    def test_locks_out_by_ip_when_spraying_multiple_usernames(self):
        for i in range(LoginThrottleService.THRESHOLD_PER_IP):
            LoginThrottleService.record(
                result=LoginAttempt.Result.INVALID_CREDENTIALS,
                attempted_username=f"conta-{i}",
                ip_address="6.6.6.6",
            )

        assert (
            LoginThrottleService.is_locked_out(
                attempted_username="conta-nova", ip_address="6.6.6.6"
            )
            is True
        )

    def test_successful_attempts_do_not_count_toward_lockout(self):
        user = User.objects.create_user(username="ok", password="senha-forte-123")
        for _ in range(LoginThrottleService.THRESHOLD_PER_USERNAME):
            LoginThrottleService.record(
                result=LoginAttempt.Result.SUCCESS,
                attempted_username="ok",
                user=user,
                ip_address="1.1.1.1",
            )

        assert (
            LoginThrottleService.is_locked_out(attempted_username="ok", ip_address="1.1.1.1")
            is False
        )


@pytest.mark.django_db
class TestPasswordResetThrottleService:
    def test_not_locked_out_with_no_requests(self):
        assert (
            PasswordResetThrottleService.is_locked_out(
                email="ninguem@example.com", ip_address="1.2.3.4"
            )
            is False
        )

    def test_locks_out_after_threshold_requests_for_same_email(self):
        for _ in range(PasswordResetThrottleService.THRESHOLD_PER_EMAIL):
            PasswordResetThrottleService.record(email="vitima@example.com", ip_address="1.2.3.4")

        assert (
            PasswordResetThrottleService.is_locked_out(
                email="vitima@example.com", ip_address="9.9.9.9"
            )
            is True
        )

    def test_locks_out_by_ip_when_spraying_multiple_emails(self):
        for i in range(PasswordResetThrottleService.THRESHOLD_PER_IP):
            PasswordResetThrottleService.record(
                email=f"conta-{i}@example.com", ip_address="6.6.6.6"
            )

        assert (
            PasswordResetThrottleService.is_locked_out(
                email="conta-nova@example.com", ip_address="6.6.6.6"
            )
            is True
        )

    def test_does_not_share_lockout_with_login_throttle(self):
        # Pedidos de recuperacao de senha nao devem contar para o throttle de LOGIN do
        # mesmo identificador — sao riscos/acoes diferentes (ver ADR).
        for _ in range(PasswordResetThrottleService.THRESHOLD_PER_EMAIL):
            PasswordResetThrottleService.record(email="joao@example.com", ip_address="1.2.3.4")

        assert (
            LoginThrottleService.is_locked_out(attempted_username="joao", ip_address="9.9.9.9")
            is False
        )
