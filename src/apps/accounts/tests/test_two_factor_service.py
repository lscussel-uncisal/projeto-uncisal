import pyotp
import pytest

from apps.accounts.models import User
from apps.accounts.services import TwoFactorService


class TestTwoFactorServiceTotp:
    def test_generated_secret_is_valid_base32(self):
        secret = TwoFactorService.generate_totp_secret()

        assert len(secret) >= 16
        pyotp.TOTP(secret).now()  # nao levanta excecao se o base32 for valido

    def test_verify_totp_accepts_the_current_code(self):
        secret = TwoFactorService.generate_totp_secret()
        current_code = pyotp.TOTP(secret).now()

        assert TwoFactorService.verify_totp(secret=secret, code=current_code) is True

    def test_verify_totp_rejects_wrong_code(self):
        secret = TwoFactorService.generate_totp_secret()

        assert TwoFactorService.verify_totp(secret=secret, code="000000") is False

    def test_verify_totp_rejects_empty_code(self):
        secret = TwoFactorService.generate_totp_secret()

        assert TwoFactorService.verify_totp(secret=secret, code="") is False

    def test_provisioning_uri_includes_issuer_and_username(self, settings):
        settings.OTP_ISSUER_NAME = "Central de Chamados"
        user = User(username="joao", email="joao@example.com")
        secret = TwoFactorService.generate_totp_secret()

        uri = TwoFactorService.provisioning_uri(user=user, secret=secret)

        assert uri.startswith("otpauth://totp/")
        assert "Central%20de%20Chamados" in uri or "Central+de+Chamados" in uri


class TestTwoFactorServiceEmailCode:
    def test_generated_code_has_six_digits(self):
        code = TwoFactorService.generate_email_code()

        assert len(code) == 6
        assert code.isdigit()

    def test_hash_code_is_deterministic_and_not_the_raw_code(self):
        code = "123456"

        hashed = TwoFactorService.hash_code(code)

        assert hashed != code
        assert hashed == TwoFactorService.hash_code(code)

    def test_hash_code_differs_for_different_codes(self):
        assert TwoFactorService.hash_code("123456") != TwoFactorService.hash_code("654321")


@pytest.mark.django_db
class TestTwoFactorServiceEmailSending:
    def test_send_email_code_sends_to_the_user_address(self, mailoutbox):
        user = User.objects.create_user(
            username="joao", password="senha-forte-123", email="joao@example.com"
        )

        TwoFactorService.send_email_code(user=user, code="123456")

        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ["joao@example.com"]
        assert "123456" in mailoutbox[0].body

    def test_send_wrong_code_alert_warns_about_possible_leak(self, mailoutbox):
        user = User.objects.create_user(
            username="joao", password="senha-forte-123", email="joao@example.com"
        )

        TwoFactorService.send_wrong_code_alert(user=user)

        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ["joao@example.com"]
        assert "senha" in mailoutbox[0].body.lower()
