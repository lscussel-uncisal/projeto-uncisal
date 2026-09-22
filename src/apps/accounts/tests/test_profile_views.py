import pytest
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
class TestProfileUpdateView:
    def test_requires_login(self, client):
        response = client.get(reverse("accounts:profile"))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_shows_current_name(self, client):
        user = User.objects.create_user(
            username="joao@example.com",
            password="senha-forte-123",
            first_name="João",
            last_name="Silva",
        )
        client.force_login(user)

        response = client.get(reverse("accounts:profile"))

        assert response.status_code == 200
        assert "João" in response.content.decode()

    def test_updates_own_name(self, client):
        user = User.objects.create_user(username="joao@example.com", password="senha-forte-123")
        client.force_login(user)

        response = client.post(
            reverse("accounts:profile"), {"first_name": "João", "last_name": "Silva"}
        )

        assert response.status_code == 302
        user.refresh_from_db()
        assert user.first_name == "João"
        assert user.last_name == "Silva"

    def test_cannot_update_someone_elses_name_via_client_data(self, client):
        user = User.objects.create_user(username="joao@example.com", password="senha-forte-123")
        other = User.objects.create_user(username="other@example.com", password="senha-forte-123")
        client.force_login(user)

        client.post(
            reverse("accounts:profile"),
            {"first_name": "Hackeado", "last_name": "X", "id": other.pk, "pk": other.pk},
        )

        other.refresh_from_db()
        assert other.first_name == ""
