from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.accounts.models import Role, User


def _create(client, actor, *, email, role, mailoutbox=None):
    client.force_login(actor)
    with patch("apps.accounts.forms.TurnstileService.verify", return_value=True):
        return client.post(
            reverse("accounts:user_create"),
            {"email": email, "first_name": "X", "last_name": "Y", "role": role},
        )


@pytest.mark.django_db
class TestSupportAndUserCannotCreateAnyone:
    def test_support_is_denied(self, client):
        support = User.objects.create_user(
            username="suporte@example.com", password="senha-forte-123", role=Role.SUPPORT
        )
        response = _create(client, support, email="novo@example.com", role=Role.USER)

        assert response.status_code == 403
        assert not User.objects.filter(email="novo@example.com").exists()

    def test_regular_user_is_denied(self, client):
        user = User.objects.create_user(username="joao@example.com", password="senha-forte-123")
        response = _create(client, user, email="novo@example.com", role=Role.USER)

        assert response.status_code == 403
        assert not User.objects.filter(email="novo@example.com").exists()


@pytest.mark.django_db
class TestAdminCannotEscalatePrivileges:
    def test_admin_can_create_admin_support_or_user(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        for i, role in enumerate((Role.ADMIN, Role.SUPPORT, Role.USER)):
            response = _create(client, admin, email=f"novo{i}@example.com", role=role)
            assert response.status_code == 302
            assert User.objects.get(email=f"novo{i}@example.com").role == role

    def test_admin_cannot_create_super_admin_even_via_forged_post(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )

        response = _create(client, admin, email="novo@example.com", role=Role.SUPER_ADMIN)

        assert response.status_code == 200
        assert not User.objects.filter(email="novo@example.com").exists()

    def test_super_admin_role_is_not_offered_in_the_form(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        client.force_login(admin)

        response = client.get(reverse("accounts:user_create"))

        role_field = response.context["form"].fields["role"]
        offered_values = [value for value, _ in role_field.choices]
        assert Role.SUPER_ADMIN not in offered_values


@pytest.mark.django_db
class TestSuperAdminCanCreateAnyone:
    def test_super_admin_can_create_another_super_admin(self, client):
        super_admin = User.objects.create_user(
            username="root@example.com", password="senha-forte-123", role=Role.SUPER_ADMIN
        )

        response = _create(client, super_admin, email="novo@example.com", role=Role.SUPER_ADMIN)

        assert response.status_code == 302
        assert User.objects.get(email="novo@example.com").role == Role.SUPER_ADMIN


@pytest.mark.django_db
class TestAdminCannotSeeOrActOnSuperAdmins:
    def test_super_admin_is_excluded_from_admins_user_list(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        User.objects.create_user(
            username="root@example.com", password="senha-forte-123", role=Role.SUPER_ADMIN
        )
        client.force_login(admin)

        response = client.get(reverse("accounts:user_list"))

        usernames = [u.username for u in response.context["users"]]
        assert "root@example.com" not in usernames
        assert "admin@example.com" in usernames

    def test_super_admin_sees_everyone_including_other_super_admins(self, client):
        super_admin = User.objects.create_user(
            username="root@example.com", password="senha-forte-123", role=Role.SUPER_ADMIN
        )
        User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        client.force_login(super_admin)

        response = client.get(reverse("accounts:user_list"))

        assert len(response.context["users"]) == 2

    def test_admin_gets_404_toggling_a_super_admin_via_direct_url(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        target = User.objects.create_user(
            username="root@example.com", password="senha-forte-123", role=Role.SUPER_ADMIN
        )
        client.force_login(admin)

        response = client.post(reverse("accounts:user_toggle_active", args=[target.pk]))

        assert response.status_code == 404
        target.refresh_from_db()
        assert target.is_active is True

    def test_super_admin_can_toggle_another_super_admin(self, client):
        super_admin = User.objects.create_user(
            username="root@example.com", password="senha-forte-123", role=Role.SUPER_ADMIN
        )
        target = User.objects.create_user(
            username="root2@example.com", password="senha-forte-123", role=Role.SUPER_ADMIN
        )
        client.force_login(super_admin)

        response = client.post(reverse("accounts:user_toggle_active", args=[target.pk]))

        assert response.status_code == 302
        target.refresh_from_db()
        assert target.is_active is False


@pytest.mark.django_db
class TestLoginReportAccessibleToSuperAdminToo:
    def test_super_admin_can_view_the_login_report(self, client):
        super_admin = User.objects.create_user(
            username="root@example.com", password="senha-forte-123", role=Role.SUPER_ADMIN
        )
        client.force_login(super_admin)

        response = client.get(reverse("accounts:login_report"))

        assert response.status_code == 200
