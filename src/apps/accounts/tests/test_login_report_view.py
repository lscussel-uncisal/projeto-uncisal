import pytest
from django.urls import reverse

from apps.accounts.models import LoginAttempt, Role, User


@pytest.mark.django_db
class TestLoginReportView:
    def test_requires_login(self, client):
        response = client.get(reverse("accounts:login_report"))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_regular_user_is_denied_even_knowing_the_route(self, client):
        user = User.objects.create_user(username="joao@example.com", password="senha-forte-123")
        client.force_login(user)

        response = client.get(reverse("accounts:login_report"))

        assert response.status_code == 403

    def test_support_is_denied(self, client):
        support = User.objects.create_user(
            username="suporte@example.com", password="senha-forte-123", role=Role.SUPPORT
        )
        client.force_login(support)

        response = client.get(reverse("accounts:login_report"))

        assert response.status_code == 403

    def test_admin_sees_every_attempt_including_unknown_usernames(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        LoginAttempt.objects.create(
            attempted_username="fantasma@example.com",
            result=LoginAttempt.Result.INVALID_CREDENTIALS,
        )
        LoginAttempt.objects.create(
            attempted_username=admin.username, user=admin, result=LoginAttempt.Result.SUCCESS
        )
        client.force_login(admin)

        response = client.get(reverse("accounts:login_report"))

        assert response.status_code == 200
        assert len(response.context["attempts"]) == 2

    def test_filter_by_result(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        LoginAttempt.objects.create(
            attempted_username="a@example.com", result=LoginAttempt.Result.INVALID_CREDENTIALS
        )
        success = LoginAttempt.objects.create(
            attempted_username=admin.username, user=admin, result=LoginAttempt.Result.SUCCESS
        )
        client.force_login(admin)

        response = client.get(
            reverse("accounts:login_report"), {"result": LoginAttempt.Result.SUCCESS}
        )

        assert list(response.context["attempts"]) == [success]

    def test_list_is_paginated(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        for i in range(35):
            LoginAttempt.objects.create(
                attempted_username=f"user{i}@example.com",
                result=LoginAttempt.Result.INVALID_CREDENTIALS,
            )
        client.force_login(admin)

        response = client.get(reverse("accounts:login_report"))

        assert response.context["is_paginated"] is True
        assert len(response.context["attempts"]) == 30
