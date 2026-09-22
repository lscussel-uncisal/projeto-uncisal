from django.db import models

from apps.core.models import TimeStampedModel


class BackupRun(TimeStampedModel):
    """Registro de cada execução de backup (manual ou agendada) — nunca guarda a chave de
    criptografia nem credencial do R2, só metadados (chave do objeto, tamanho, erro)."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Sucesso"
        FAILED = "failed", "Falha"

    status = models.CharField(max_length=10, choices=Status.choices)
    object_key = models.CharField(max_length=255, blank=True)
    size_bytes = models.BigIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.get_status_display()} - {self.created_at:%Y-%m-%d %H:%M}"
