import pytest
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_healthz_returns_ok(client):
    response = client.get(reverse("healthz"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
class TestHomeRedirect:
    def test_anonymous_visitor_is_sent_to_login(self, client):
        response = client.get("/")

        assert response.status_code == 302
        assert response.url == f"{reverse('accounts:login')}?next={reverse('tickets:list')}"

    def test_logged_in_user_is_sent_to_ticket_list(self, client):
        user = User.objects.create_user(username="joao", password="senha-forte-123")
        client.force_login(user)

        response = client.get("/")

        assert response.status_code == 302
        assert response.url == reverse("tickets:list")
