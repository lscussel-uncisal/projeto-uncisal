from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Status(models.TextChoices):
    OPEN = "open", "Aberto"
    IN_PROGRESS = "in_progress", "Em andamento"
    RESOLVED = "resolved", "Resolvido"
    CLOSED = "closed", "Fechado"


class Priority(models.TextChoices):
    LOW = "low", "Baixa"
    MEDIUM = "medium", "Média"
    HIGH = "high", "Alta"


class Ticket(TimeStampedModel):
    """Chamado registrado por um usuário e opcionalmente direcionado a um agente de suporte."""

    title = models.CharField("Título", max_length=150)
    description = models.TextField("Descrição")
    status = models.CharField("Status", max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(
        "Prioridade", max_length=10, choices=Priority.choices, default=Priority.MEDIUM
    )

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="requested_tickets",
        verbose_name="Solicitante",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
        verbose_name="Responsável",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"#{self.pk} - {self.title}"
