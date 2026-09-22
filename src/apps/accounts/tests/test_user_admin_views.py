import pytest
from django.urls import reverse

from apps.accounts.models import Role, User


@pytest.mark.django_db
class TestUserListView:
    def test_requires_login(self, client):
        response = client.get(reverse("accounts:user_list"))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_regular_user_is_denied_even_knowing_the_route(self, client):
        user = User.objects.create_user(username="joao@example.com", password="senha-forte-123")
        client.force_login(user)

        response = client.get(reverse("accounts:user_list"))

        assert response.status_code == 403

    def test_support_is_denied(self, client):
        support = User.objects.create_user(
            username="suporte@example.com", password="senha-forte-123", role=Role.SUPPORT
        )
        client.force_login(support)

        response = client.get(reverse("accounts:user_list"))

        assert response.status_code == 403

    def test_admin_can_view_every_user(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        User.objects.create_user(username="joao@example.com", password="senha-forte-123")
        client.force_login(admin)

        response = client.get(reverse("accounts:user_list"))

        assert response.status_code == 200
        assert len(response.context["users"]) == 2


@pytest.mark.django_db
class TestUserToggleActiveView:
    def test_requires_login(self, client):
        target = User.objects.create_user(username="joao@example.com", password="senha-forte-123")

        response = client.post(reverse("accounts:user_toggle_active", args=[target.pk]))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_regular_user_is_denied(self, client):
        user = User.objects.create_user(username="joao@example.com", password="senha-forte-123")
        target = User.objects.create_user(username="other@example.com", password="senha-forte-123")
        client.force_login(user)

        response = client.post(reverse("accounts:user_toggle_active", args=[target.pk]))

        assert response.status_code == 403
        target.refresh_from_db()
        assert target.is_active is True

    def test_support_is_denied(self, client):
        support = User.objects.create_user(
            username="suporte@example.com", password="senha-forte-123", role=Role.SUPPORT
        )
        target = User.objects.create_user(username="joao@example.com", password="senha-forte-123")
        client.force_login(support)

        response = client.post(reverse("accounts:user_toggle_active", args=[target.pk]))

        assert response.status_code == 403
        target.refresh_from_db()
        assert target.is_active is True

    def test_get_is_not_allowed(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        target = User.objects.create_user(username="joao@example.com", password="senha-forte-123")
        client.force_login(admin)

        response = client.get(reverse("accounts:user_toggle_active", args=[target.pk]))

        assert response.status_code == 405

    def test_admin_can_deactivate_another_user(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        target = User.objects.create_user(username="joao@example.com", password="senha-forte-123")
        client.force_login(admin)

        response = client.post(reverse("accounts:user_toggle_active", args=[target.pk]))

        assert response.status_code == 302
        target.refresh_from_db()
        assert target.is_active is False

    def test_admin_can_reactivate_a_deactivated_user(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        target = User.objects.create_user(
            username="joao@example.com", password="senha-forte-123", is_active=False
        )
        client.force_login(admin)

        client.post(reverse("accounts:user_toggle_active", args=[target.pk]))

        target.refresh_from_db()
        assert target.is_active is True

    def test_admin_cannot_deactivate_their_own_account(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        client.force_login(admin)

        response = client.post(reverse("accounts:user_toggle_active", args=[admin.pk]))

        assert response.status_code == 400
        admin.refresh_from_db()
        assert admin.is_active is True
