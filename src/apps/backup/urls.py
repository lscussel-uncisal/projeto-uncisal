from django.urls import path

from apps.backup.views import BackupStatusView, backup_run_now

app_name = "backup"

urlpatterns = [
    path("", BackupStatusView.as_view(), name="status"),
    path("agora/", backup_run_now, name="run_now"),
]
