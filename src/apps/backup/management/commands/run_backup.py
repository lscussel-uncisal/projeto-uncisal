import sys

from django.core.management.base import BaseCommand

from apps.backup.models import BackupRun
from apps.backup.services import BackupService


class Command(BaseCommand):
    """Roda um backup completo e sai com código != 0 se falhar — usado tanto manualmente
    quanto pelo sidecar de agendamento (ver docker/scripts/backup-scheduler.sh)."""

    help = "Executa um backup completo do banco e envia para o Cloudflare R2."

    def handle(self, *args, **options):
        run = BackupService.run_full_backup()
        if run.status == BackupRun.Status.SUCCESS:
            self.stdout.write(
                self.style.SUCCESS(f"Backup OK: {run.object_key} ({run.size_bytes} bytes)")
            )
        else:
            self.stderr.write(self.style.ERROR(f"Backup falhou: {run.error_message}"))
            sys.exit(1)
