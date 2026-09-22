from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic import ListView

from apps.accounts.models import Role
from apps.accounts.permissions import role_required
from apps.backup.models import BackupRun
from apps.backup.services import BackupService


@method_decorator(role_required(Role.ADMIN, Role.SUPER_ADMIN), name="dispatch")
class BackupStatusView(ListView):
    """Histórico de execuções de backup + botão de backup imediato. Mesma proteção
    server-side das outras telas de administração."""

    model = BackupRun
    template_name = "backup/status.html"
    context_object_name = "runs"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["backup_enabled"] = settings.BACKUP_ENABLED
        context["backup_prefix"] = settings.R2_BACKUP_PREFIX
        context["retention_count"] = settings.BACKUP_RETENTION_COUNT
        return context


@role_required(Role.ADMIN, Role.SUPER_ADMIN)
@require_POST
def backup_run_now(request):
    """Dispara um backup completo na hora. Síncrono de propósito — o banco deste projeto é
    pequeno o bastante pra terminar dentro do tempo de uma requisição HTTP normal; não vale
    a complexidade de fila assíncrona (Celery etc.) pra esse volume de dados."""
    run = BackupService.run_full_backup()
    if run.status == BackupRun.Status.SUCCESS:
        messages.success(request, "Backup concluído com sucesso.")
    else:
        messages.error(request, f"Falha no backup: {run.error_message}")
    return redirect("backup:status")
