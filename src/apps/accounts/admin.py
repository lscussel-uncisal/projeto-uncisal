from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.accounts.models import LoginAttempt, TwoFactorDevice, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """`is_active` já vem do UserAdmin padrão do Django (fieldset "Permissions") — um
    usuário desativado não consegue logar (`ModelBackend.authenticate` já checa isso) nem
    usar a recuperação de senha (`PasswordResetRequestView` também checa, ver services.py).
    Só deixamos mais visível na listagem/filtro aqui, pra não precisar abrir cada usuário
    pra saber se está ativo."""

    fieldsets = UserAdmin.fieldsets + (
        ("Papel (RBAC)", {"fields": ("role", "is_two_factor_enabled")}),
    )
    list_display = ("username", "email", "role", "is_active", "is_two_factor_enabled", "is_staff")
    list_filter = ("role", "is_active", "is_two_factor_enabled", "is_staff")


@admin.register(TwoFactorDevice)
class TwoFactorDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "method", "confirmed", "updated_at")
    list_filter = ("method", "confirmed")


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "result", "ip_address", "created_at")
    list_filter = ("result",)
    readonly_fields = [f.name for f in LoginAttempt._meta.fields]
