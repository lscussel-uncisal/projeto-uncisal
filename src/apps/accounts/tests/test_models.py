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

    def test_display_name_uses_full_name_when_set(self):
        user = User.objects.create_user(
            username="joao@example.com",
            password="senha-forte-123",
            first_name="João",
            last_name="Silva",
        )

        assert user.display_name == "João Silva"

    def test_display_name_falls_back_to_local_part_of_username_never_full_email(self):
        user = User.objects.create_user(
            username="joao.silva@example.com", password="senha-forte-123"
        )

        assert user.display_name == "joao.silva"
        assert "@" not in user.display_name
        assert "example.com" not in user.display_name

    def test_str_never_exposes_the_email(self):
        user = User.objects.create_user(username="joao@example.com", password="senha-forte-123")

        assert str(user) == "joao"
        assert "@" not in str(user)
