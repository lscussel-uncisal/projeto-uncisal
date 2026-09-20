from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _fernet() -> Fernet:
    return Fernet(settings.FIELD_ENCRYPTION_KEY)


class EncryptedCharField(models.CharField):
    """CharField que criptografa o valor antes de gravar e descriptografa ao ler.

    Usa Fernet (AES-128-CBC + HMAC — criptografia autenticada), com chave dedicada
    em settings.FIELD_ENCRYPTION_KEY (separada da SECRET_KEY do Django).

    Falha explicitamente se a chave estiver errada ou o dado estiver corrompido —
    nunca retorna um valor "provavelmente certo" por fallback silencioso.
    """

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if not value:
            return value
        return _fernet().encrypt(value.encode()).decode()

    def from_db_value(self, value, expression, connection):
        if not value:
            return value
        try:
            return _fernet().decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise ValueError(
                "Falha ao descriptografar campo: FIELD_ENCRYPTION_KEY incorreta ou dado corrompido."
            ) from exc
