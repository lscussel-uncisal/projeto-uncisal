from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from apps.backup.models import BackupRun
from apps.backup.services import BackupService

VALID_R2_SETTINGS = {
    "R2_ACCOUNT_ID": "acc123",
    "R2_ACCESS_KEY_ID": "key123",
    "R2_SECRET_ACCESS_KEY": "secret123",
    "R2_BUCKET_NAME": "bkp-bucket",
    "R2_BACKUP_PREFIX": "bkp_uncisal",
    "BACKUP_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "BACKUP_ENABLED": True,
    "BACKUP_RETENTION_COUNT": 7,
}


@pytest.fixture
def r2_configured(settings):
    for name, value in VALID_R2_SETTINGS.items():
        setattr(settings, name, value)
    return settings


@pytest.mark.django_db
class TestBackupServiceDisabled:
    def test_refuses_to_run_when_not_configured(self, settings):
        settings.BACKUP_ENABLED = False

        run = BackupService.run_full_backup()

        assert run.status == BackupRun.Status.FAILED
        assert "não está configurado" in run.error_message.lower()


@pytest.mark.django_db
class TestBackupServiceUploadFlow:
    def test_successful_backup_uploads_an_encrypted_object_and_logs_success(self, r2_configured):
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {"Contents": []}

        with patch("apps.backup.services.boto3.client", return_value=mock_client):
            run = BackupService.run_full_backup()

        assert run.status == BackupRun.Status.SUCCESS
        assert run.object_key.startswith("bkp_uncisal/db-")
        assert run.object_key.endswith(".sqlite3.enc")
        assert run.size_bytes > 0
        mock_client.upload_file.assert_called_once()
        uploaded_path, bucket, key = mock_client.upload_file.call_args[0]
        assert bucket == "bkp-bucket"
        assert key == run.object_key

    def test_uploaded_content_is_encrypted_not_a_raw_sqlite_file(self, r2_configured):
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {"Contents": []}
        captured = {}

        def fake_upload_file(local_path, bucket, key):
            captured["bytes"] = open(local_path, "rb").read()

        mock_client.upload_file.side_effect = fake_upload_file

        with patch("apps.backup.services.boto3.client", return_value=mock_client):
            BackupService.run_full_backup()

        assert not captured["bytes"].startswith(b"SQLite format 3")
        fernet = Fernet(VALID_R2_SETTINGS["BACKUP_ENCRYPTION_KEY"].encode())
        decrypted = fernet.decrypt(captured["bytes"])
        assert decrypted.startswith(b"SQLite format 3")

    def test_upload_failure_is_recorded_not_raised(self, r2_configured):
        mock_client = MagicMock()
        mock_client.upload_file.side_effect = RuntimeError("R2 unreachable")

        with patch("apps.backup.services.boto3.client", return_value=mock_client):
            run = BackupService.run_full_backup()

        assert run.status == BackupRun.Status.FAILED
        assert "R2 unreachable" in run.error_message

    def test_retention_deletes_objects_beyond_the_configured_count(self, r2_configured):
        r2_configured.BACKUP_RETENTION_COUNT = 2
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "bkp_uncisal/db-3.sqlite3.enc", "LastModified": 3},
                {"Key": "bkp_uncisal/db-1.sqlite3.enc", "LastModified": 1},
                {"Key": "bkp_uncisal/db-2.sqlite3.enc", "LastModified": 2},
            ]
        }

        with patch("apps.backup.services.boto3.client", return_value=mock_client):
            BackupService.run_full_backup()

        deleted_keys = {call.kwargs["Key"] for call in mock_client.delete_object.call_args_list}
        assert deleted_keys == {"bkp_uncisal/db-1.sqlite3.enc"}
