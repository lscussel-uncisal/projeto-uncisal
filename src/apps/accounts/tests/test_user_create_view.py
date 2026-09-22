import pytest
from django.urls import reverse

from apps.accounts.models import Role, User


@pytest.mark.django_db
class TestUserCreateView:
    def test_requires_login(self, client):
        response = client.get(reverse("accounts:user_create"))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_regular_user_is_denied(self, client):
        user = User.objects.create_user(username="joao@example.com", password="senha-forte-123")
        client.force_login(user)

        response = client.get(reverse("accounts:user_create"))

        assert response.status_code == 403

    def test_support_is_denied(self, client):
        support = User.objects.create_user(
            username="suporte@example.com", password="senha-forte-123", role=Role.SUPPORT
        )
        client.force_login(support)

        response = client.get(reverse("accounts:user_create"))

        assert response.status_code == 403

    def test_admin_can_create_a_user(self, client, mailoutbox):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        client.force_login(admin)

        response = client.post(
            reverse("accounts:user_create"),
            {
                "email": "novo@example.com",
                "first_name": "Novo",
                "last_name": "Usuário",
                "role": Role.USER,
            },
        )

        assert response.status_code == 302
        created = User.objects.get(email="novo@example.com")
        assert created.username == "novo@example.com"
        assert created.role == Role.USER
        assert created.is_active is True

    def test_new_user_has_no_usable_password_and_is_emailed_instructions(self, client, mailoutbox):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        client.force_login(admin)

        client.post(
            reverse("accounts:user_create"),
            {
                "email": "novo@example.com",
                "first_name": "Novo",
                "last_name": "Usuário",
                "role": Role.USER,
            },
        )

        created = User.objects.get(email="novo@example.com")
        assert created.has_usable_password() is False
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ["novo@example.com"]

    def test_cannot_create_duplicate_email(self, client, mailoutbox):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        User.objects.create_user(
            username="novo@example.com", password="senha-forte-123", email="novo@example.com"
        )
        client.force_login(admin)

        response = client.post(
            reverse("accounts:user_create"),
            {
                "email": "novo@example.com",
                "first_name": "X",
                "last_name": "Y",
                "role": Role.USER,
            },
        )

        assert response.status_code == 200
        assert User.objects.filter(email="novo@example.com").count() == 1
        assert len(mailoutbox) == 0
