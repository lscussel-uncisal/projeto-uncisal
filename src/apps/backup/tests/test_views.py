from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.backup.models import BackupRun


@pytest.mark.django_db
class TestBackupStatusView:
    def test_requires_login(self, client):
        response = client.get(reverse("backup:status"))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_regular_user_is_denied(self, client):
        user = User.objects.create_user(username="joao@example.com", password="senha-forte-123")
        client.force_login(user)

        response = client.get(reverse("backup:status"))

        assert response.status_code == 403

    def test_support_is_denied(self, client):
        support = User.objects.create_user(
            username="suporte@example.com", password="senha-forte-123", role=Role.SUPPORT
        )
        client.force_login(support)

        response = client.get(reverse("backup:status"))

        assert response.status_code == 403

    def test_admin_can_view_the_status_page(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        client.force_login(admin)

        response = client.get(reverse("backup:status"))

        assert response.status_code == 200
        assert response.context["backup_enabled"] is False

    def test_super_admin_can_view_the_status_page(self, client):
        super_admin = User.objects.create_user(
            username="root@example.com", password="senha-forte-123", role=Role.SUPER_ADMIN
        )
        client.force_login(super_admin)

        response = client.get(reverse("backup:status"))

        assert response.status_code == 200


@pytest.mark.django_db
class TestBackupRunNowView:
    def test_requires_login(self, client):
        response = client.post(reverse("backup:run_now"))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_regular_user_is_denied(self, client):
        user = User.objects.create_user(username="joao@example.com", password="senha-forte-123")
        client.force_login(user)

        response = client.post(reverse("backup:run_now"))

        assert response.status_code == 403

    def test_get_is_not_allowed(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        client.force_login(admin)

        response = client.get(reverse("backup:run_now"))

        assert response.status_code == 405

    def test_admin_triggering_it_without_r2_configured_records_a_failed_run(self, client):
        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        client.force_login(admin)

        response = client.post(reverse("backup:run_now"))

        assert response.status_code == 302
        assert BackupRun.objects.count() == 1
        assert BackupRun.objects.first().status == BackupRun.Status.FAILED

    @pytest.mark.django_db(transaction=True)
    def test_admin_triggering_a_successful_backup(self, client, settings):
        # transaction=True (em vez do django_db padrão da classe, que embrulha o teste numa
        # transação nunca commitada): essa view chama BackupService._snapshot_database, que
        # abre uma conexão sqlite3 própria pro MESMO arquivo — com a transação da classe de
        # teste aberta, essa segunda conexão trava esperando lock (nunca solta, porque a
        # transação de teste nunca commita). Com transaction=True o Django usa commit/reset
        # de verdade entre testes, sem segurar transação aberta, igual ao comportamento real
        # em produção (que roda em autocommit fora de atomic()).
        from cryptography.fernet import Fernet

        settings.R2_ACCOUNT_ID = "acc123"
        settings.R2_ACCESS_KEY_ID = "key123"
        settings.R2_SECRET_ACCESS_KEY = "secret123"
        settings.R2_BUCKET_NAME = "bkp-bucket"
        settings.BACKUP_ENCRYPTION_KEY = Fernet.generate_key().decode()
        settings.BACKUP_ENABLED = True

        admin = User.objects.create_user(
            username="admin@example.com", password="senha-forte-123", role=Role.ADMIN
        )
        client.force_login(admin)

        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {"Contents": []}
        with patch("apps.backup.services.boto3.client", return_value=mock_client):
            response = client.post(reverse("backup:run_now"))

        assert response.status_code == 302
        assert BackupRun.objects.first().status == BackupRun.Status.SUCCESS
