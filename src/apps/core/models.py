from django.db import models


class TimeStampedModel(models.Model):
    """Base abstrata com auditoria minima de criacao/atualizacao (DRY entre apps)."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
