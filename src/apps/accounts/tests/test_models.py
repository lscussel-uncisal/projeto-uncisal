import pytest

from apps.accounts.models import Role, User


@pytest.mark.django_db
class TestUser:
    def test_default_role_is_user(self):
        user = User.objects.create_user(username="joao", password="senha-forte-123")

        assert user.role == Role.USER
        assert user.is_admin_role is False
        assert user.is_support_role is False

    def test_admin_role_flags(self):
        admin = User.objects.create_user(
            username="admin", password="senha-forte-123", role=Role.ADMIN
        )

        assert admin.is_admin_role is True
        assert admin.is_support_role is False

    def test_two_factor_disabled_by_default(self):
        user = User.objects.create_user(username="maria", password="senha-forte-123")

        assert user.is_two_factor_enabled is False
