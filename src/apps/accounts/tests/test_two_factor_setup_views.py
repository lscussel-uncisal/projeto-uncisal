from unittest.mock import patch

import pyotp
import pytest
from django.urls import reverse

from apps.accounts.models import TwoFactorDevice, TwoFactorMethod, User


@pytest.fixture
def logged_in_client(client):
    user = User.objects.create_user(
        username="joao", password="senha-forte-123", email="joao@example.com"
    )
    client.force_login(user)
    return client, user


@pytest.mark.django_db
class TestTwoFactorSetupView:
    def test_choosing_totp_creates_an_unconfirmed_device_and_redirects_to_confirm(
        self, logged_in_client
    ):
        client, user = logged_in_client

        response = client.post(reverse("accounts:two_factor_setup"), {"method": "totp"})

        assert response.status_code == 302
        assert response.url == reverse("accounts:two_factor_confirm")
        device = TwoFactorDevice.objects.get(user=user)
        assert device.method == TwoFactorMethod.TOTP
        assert device.confirmed is False
        assert device.totp_secret

    def test_choosing_email_sends_a_code_and_redirects_to_confirm(
        self, logged_in_client, mailoutbox
    ):
        client, user = logged_in_client

        response = client.post(reverse("accounts:two_factor_setup"), {"method": "email"})

        assert response.status_code == 302
        assert response.url == reverse("accounts:two_factor_confirm")
        device = TwoFactorDevice.objects.get(user=user)
        assert device.method == TwoFactorMethod.EMAIL
        assert device.confirmed is False
        assert len(mailoutbox) == 1

    def test_disabling_turns_off_the_flag_and_unconfirms_the_device(self, logged_in_client):
        client, user = logged_in_client
        TwoFactorDevice.objects.create(
            user=user, method=TwoFactorMethod.TOTP, totp_secret="ABCDEFGHIJKLMNOP", confirmed=True
        )
        user.is_two_factor_enabled = True
        user.save()

        response = client.post(reverse("accounts:two_factor_setup"), {"action": "disable"})

        assert response.status_code == 302
        user.refresh_from_db()
        assert user.is_two_factor_enabled is False
        assert TwoFactorDevice.objects.get(user=user).confirmed is False

    def test_requires_login(self, client):
        response = client.get(reverse("accounts:two_factor_setup"))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_smtp_failure_shows_error_and_does_not_create_a_pending_device(self, logged_in_client):
        client, user = logged_in_client

        with patch("apps.accounts.views.TwoFactorService.send_email_code", return_value=False):
            response = client.post(reverse("accounts:two_factor_setup"), {"method": "email"})

        assert response.status_code == 200
        assert b"e-mail" in response.content
        assert "2fa_setup_email_code_hash" not in client.session


@pytest.mark.django_db
class TestTwoFactorConfirmSetupView:
    def test_cannot_access_confirm_without_a_pending_device(self, logged_in_client):
        client, _user = logged_in_client

        response = client.get(reverse("accounts:two_factor_confirm"))

        assert response.status_code == 302
        assert response.url == reverse("accounts:two_factor_setup")

    def test_correct_totp_code_confirms_the_device_and_enables_2fa(self, logged_in_client):
        client, user = logged_in_client
        secret = pyotp.random_base32()
        TwoFactorDevice.objects.create(
            user=user, method=TwoFactorMethod.TOTP, totp_secret=secret, confirmed=False
        )

        response = client.post(
            reverse("accounts:two_factor_confirm"), {"code": pyotp.TOTP(secret).now()}
        )

        assert response.status_code == 302
        user.refresh_from_db()
        assert user.is_two_factor_enabled is True
        assert TwoFactorDevice.objects.get(user=user).confirmed is True

    def test_wrong_totp_code_does_not_confirm(self, logged_in_client):
        client, user = logged_in_client
        secret = pyotp.random_base32()
        TwoFactorDevice.objects.create(
            user=user, method=TwoFactorMethod.TOTP, totp_secret=secret, confirmed=False
        )

        response = client.post(reverse("accounts:two_factor_confirm"), {"code": "000000"})

        assert response.status_code == 200
        user.refresh_from_db()
        assert user.is_two_factor_enabled is False
        assert TwoFactorDevice.objects.get(user=user).confirmed is False

    def test_correct_email_code_confirms_the_device(self, logged_in_client, mailoutbox):
        client, user = logged_in_client
        client.post(reverse("accounts:two_factor_setup"), {"method": "email"})
        sent_code = mailoutbox[0].body.split("é: ")[1].split("\n")[0]

        response = client.post(reverse("accounts:two_factor_confirm"), {"code": sent_code})

        assert response.status_code == 302
        user.refresh_from_db()
        assert user.is_two_factor_enabled is True

    def test_get_shows_qr_code_for_totp_method(self, logged_in_client):
        client, user = logged_in_client
        TwoFactorDevice.objects.create(
            user=user,
            method=TwoFactorMethod.TOTP,
            totp_secret=pyotp.random_base32(),
            confirmed=False,
        )

        response = client.get(reverse("accounts:two_factor_confirm"))

        assert response.status_code == 200
        assert b"data:image/png;base64," in response.content
