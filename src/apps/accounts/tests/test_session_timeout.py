import time
from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.urls import reverse
from django.utils import timezone

from apps.accounts.middleware import SESSION_AUTH_STARTED_AT
from apps.accounts.models import User

PROTECTED_URL = "tickets:list"


@pytest.fixture
def logged_client(client):
    user = User.objects.create_user(username="ana", password="senha-forte-123")
    client.force_login(user)
    return client


def _set_session_start(client, seconds_ago):
    session = client.session
    session[SESSION_AUTH_STARTED_AT] = time.time() - seconds_ago
    session.save()


def _set_idle_deadline(client, deadline):
    Session.objects.filter(session_key=client.session.session_key).update(expire_date=deadline)


@pytest.mark.django_db
class TestIdleTimeout:
    def test_idle_timeout_is_30_minutes_counted_from_the_last_request(self):
        assert settings.SESSION_COOKIE_AGE == 30 * 60
        assert settings.SESSION_SAVE_EVERY_REQUEST is True

    def test_each_request_pushes_the_idle_deadline_forward(self, logged_client):
        _set_idle_deadline(logged_client, timezone.now() + timedelta(minutes=1))

        logged_client.get(reverse(PROTECTED_URL))

        session = Session.objects.get(session_key=logged_client.session.session_key)
        assert session.expire_date > timezone.now() + timedelta(minutes=29)

    def test_session_idle_past_the_deadline_is_sent_back_to_login(self, logged_client):
        _set_idle_deadline(logged_client, timezone.now() - timedelta(seconds=1))

        response = logged_client.get(reverse(PROTECTED_URL))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_logout_deletes_the_session_on_the_server(self, logged_client):
        logged_client.get(reverse(PROTECTED_URL))
        old_key = logged_client.session.session_key

        logged_client.post(reverse("accounts:logout"))

        assert not Session.objects.filter(session_key=old_key).exists()

    def test_session_cookie_is_discarded_when_the_browser_closes(self, logged_client):
        response = logged_client.get(reverse(PROTECTED_URL))

        cookie = response.cookies[settings.SESSION_COOKIE_NAME]
        assert cookie["max-age"] == ""
        assert cookie["expires"] == ""


@pytest.mark.django_db
class TestAbsoluteTimeout:
    def test_absolute_limit_is_8_hours(self):
        assert settings.SESSION_ABSOLUTE_TIMEOUT == 8 * 60 * 60

    def test_first_authenticated_request_records_when_the_session_started(self, logged_client):
        before = time.time()

        logged_client.get(reverse(PROTECTED_URL))

        assert logged_client.session[SESSION_AUTH_STARTED_AT] >= before

    def test_active_session_within_the_limit_is_kept(self, logged_client):
        _set_session_start(logged_client, seconds_ago=7 * 60 * 60)

        response = logged_client.get(reverse(PROTECTED_URL))

        assert response.status_code == 200

    def test_active_session_past_the_limit_is_logged_out_on_the_server(self, logged_client):
        _set_session_start(logged_client, seconds_ago=settings.SESSION_ABSOLUTE_TIMEOUT + 1)
        old_key = logged_client.session.session_key

        response = logged_client.get(reverse(PROTECTED_URL))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url
        assert not Session.objects.filter(session_key=old_key).exists()
        assert logged_client.get(reverse(PROTECTED_URL)).status_code == 302

    def test_user_is_told_why_they_were_sent_to_login(self, logged_client):
        _set_session_start(logged_client, seconds_ago=settings.SESSION_ABSOLUTE_TIMEOUT + 1)

        response = logged_client.get(reverse(PROTECTED_URL), follow=True)

        assert "Sua sessão expirou" in response.content.decode()

    def test_anonymous_requests_are_untouched(self, client):
        response = client.get(reverse("accounts:login"))

        assert response.status_code == 200
        assert SESSION_AUTH_STARTED_AT not in client.session
