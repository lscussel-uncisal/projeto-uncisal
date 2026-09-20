import pytest
from django.db import connection

from apps.accounts.models import TwoFactorDevice, TwoFactorMethod, User

RAW_SECRET = "JBSWY3DPEHPK3PXP"


@pytest.mark.django_db
class TestEncryptedCharField:
    def test_round_trip_via_orm(self):
        user = User.objects.create_user(username="totp-user", password="senha-forte-123")
        device = TwoFactorDevice.objects.create(
            user=user, method=TwoFactorMethod.TOTP, totp_secret=RAW_SECRET
        )

        reloaded = TwoFactorDevice.objects.get(pk=device.pk)

        assert reloaded.totp_secret == RAW_SECRET

    def test_value_is_actually_encrypted_at_rest(self):
        user = User.objects.create_user(username="totp-user-2", password="senha-forte-123")
        device = TwoFactorDevice.objects.create(
            user=user, method=TwoFactorMethod.TOTP, totp_secret=RAW_SECRET
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT totp_secret FROM accounts_twofactordevice WHERE id = %s", [device.pk]
            )
            raw_db_value = cursor.fetchone()[0]

        assert raw_db_value != RAW_SECRET
        assert RAW_SECRET not in raw_db_value

    def test_blank_value_is_not_encrypted(self):
        user = User.objects.create_user(username="totp-user-3", password="senha-forte-123")
        device = TwoFactorDevice.objects.create(
            user=user, method=TwoFactorMethod.EMAIL, totp_secret=""
        )

        reloaded = TwoFactorDevice.objects.get(pk=device.pk)

        assert reloaded.totp_secret == ""
