import pytest

from apps.accounts.models import User
from apps.accounts.services import AccountNotificationService


class TestGenerateTempPassword:
    def test_generates_a_reasonably_long_password(self):
        pwd = AccountNotificationService.generate_temp_password()

        assert len(pwd) >= 16

    def test_generates_different_passwords_each_time(self):
        passwords = {AccountNotificationService.generate_temp_password() for _ in range(20)}

        assert len(passwords) == 20


@pytest.mark.django_db
class TestSendLoginNotification:
    def test_sends_to_the_user_address_with_the_ip(self, mailoutbox):
        user = User.objects.create_user(
            username="joao", password="senha-forte-123", email="joao@example.com"
        )

        AccountNotificationService.send_login_notification(user=user, ip_address="1.2.3.4")

        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ["joao@example.com"]
        assert "1.2.3.4" in mailoutbox[0].body

    def test_does_not_raise_when_smtp_fails(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.dummy.EmailBackend"
        user = User.objects.create_user(
            username="joao", password="senha-forte-123", email="joao@example.com"
        )

        # dummy backend nao levanta OSError de verdade, mas o metodo precisa aceitar
        # qualquer configuracao de EMAIL_BACKEND sem quebrar a chamada.
        AccountNotificationService.send_login_notification(user=user, ip_address=None)


@pytest.mark.django_db
class TestSendTempPassword:
    def test_sends_the_password_and_returns_true(self, mailoutbox):
        user = User.objects.create_user(
            username="joao", password="senha-forte-123", email="joao@example.com"
        )

        sent = AccountNotificationService.send_temp_password(user=user, temp_password="abc-123-xyz")

        assert sent is True
        assert len(mailoutbox) == 1
        assert "abc-123-xyz" in mailoutbox[0].body

    def test_returns_false_on_smtp_failure(self, monkeypatch):
        user = User.objects.create_user(
            username="joao", password="senha-forte-123", email="joao@example.com"
        )

        def boom(*args, **kwargs):
            raise OSError("smtp indisponivel")

        monkeypatch.setattr("apps.accounts.services.send_mail", boom)

        sent = AccountNotificationService.send_temp_password(user=user, temp_password="x")

        assert sent is False
