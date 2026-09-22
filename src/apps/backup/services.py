import logging
import sqlite3
import tempfile
from pathlib import Path

import boto3
from cryptography.fernet import Fernet
from django.conf import settings
from django.db import connection
from django.utils import timezone

from apps.backup.models import BackupRun

logger = logging.getLogger(__name__)


class BackupService:
    """Backup completo do banco: snapshot consistente via API nativa do SQLite, cifrado com
    uma chave Fernet dedicada (nunca reaproveita FIELD_ENCRYPTION_KEY, usada só pro TOTP —
    propósitos diferentes não compartilham chave), enviado pro Cloudflare R2. Qualquer falha
    vira um BackupRun com status=FAILED, nunca uma exceção não tratada — tanto o botão
    "backup agora" quanto o job agendado precisam sempre terminar com um registro, não um 500
    nem um processo que morre silenciosamente."""

    @staticmethod
    def _r2_client():
        return boto3.client(
            "s3",
            endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        )

    @staticmethod
    def _snapshot_database(destination: Path) -> None:
        """sqlite3 .backup nativo — consistente mesmo com o banco em uso (ao contrário de
        copiar o arquivo direto, que pode capturar uma escrita no meio do caminho).

        Abre uma conexão própria, separada da conexão do Django, de propósito: reaproveitar
        `connection.connection` (a conexão que o Django já tem aberta) trava esperando lock
        quando essa conexão está no meio de uma transação — em produção isso é raro (Django
        roda em autocommit fora de `atomic()`), mas nos testes (`@pytest.mark.django_db`
        embrulha cada teste numa transação nunca commitada) é garantido. Ver
        TestBackupRunNowView.test_admin_triggering_a_successful_backup, que usa
        `django_db(transaction=True)` justamente para não segurar essa transação aberta."""
        source = sqlite3.connect(connection.settings_dict["NAME"])
        dest = sqlite3.connect(str(destination))
        with dest:
            source.backup(dest)
        source.close()
        dest.close()

    @staticmethod
    def _encrypt_file(source: Path, destination: Path) -> None:
        fernet = Fernet(settings.BACKUP_ENCRYPTION_KEY.encode())
        destination.write_bytes(fernet.encrypt(source.read_bytes()))

    @classmethod
    def _enforce_retention(cls, client) -> None:
        """Mantém só os BACKUP_RETENTION_COUNT objetos mais recentes no prefixo — backup sem
        limite de retenção cresce pra sempre e custa dinheiro/espaço indefinidamente."""
        response = client.list_objects_v2(
            Bucket=settings.R2_BUCKET_NAME, Prefix=f"{settings.R2_BACKUP_PREFIX}/"
        )
        objects = sorted(
            response.get("Contents", []), key=lambda obj: obj["LastModified"], reverse=True
        )
        for obsolete in objects[settings.BACKUP_RETENTION_COUNT :]:
            client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=obsolete["Key"])

    @classmethod
    def run_full_backup(cls) -> BackupRun:
        if not settings.BACKUP_ENABLED:
            return BackupRun.objects.create(
                status=BackupRun.Status.FAILED,
                error_message=(
                    "Backup não está configurado (faltam variáveis de ambiente do R2 — "
                    "ver docs/security/backup-recovery.md)."
                ),
            )

        timestamp = timezone.now().strftime("%Y%m%d-%H%M%S")
        object_key = f"{settings.R2_BACKUP_PREFIX}/db-{timestamp}.sqlite3.enc"

        try:
            with tempfile.TemporaryDirectory() as tmp:
                snapshot = Path(tmp) / "db.sqlite3"
                encrypted = Path(tmp) / "db.sqlite3.enc"
                cls._snapshot_database(snapshot)
                cls._encrypt_file(snapshot, encrypted)
                size = encrypted.stat().st_size

                client = cls._r2_client()
                client.upload_file(str(encrypted), settings.R2_BUCKET_NAME, object_key)
                cls._enforce_retention(client)

            return BackupRun.objects.create(
                status=BackupRun.Status.SUCCESS, object_key=object_key, size_bytes=size
            )
        except Exception as exc:
            logger.error("Falha ao executar backup", exc_info=True)
            return BackupRun.objects.create(
                status=BackupRun.Status.FAILED, error_message=str(exc)[:500]
            )
