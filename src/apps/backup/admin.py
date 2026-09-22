from django.contrib import admin

from apps.backup.models import BackupRun


@admin.register(BackupRun)
class BackupRunAdmin(admin.ModelAdmin):
    list_display = ("status", "object_key", "size_bytes", "created_at")
    list_filter = ("status",)
    readonly_fields = [f.name for f in BackupRun._meta.fields]
