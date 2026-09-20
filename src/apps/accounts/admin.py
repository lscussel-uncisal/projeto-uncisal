from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.accounts.models import LoginAttempt, TwoFactorDevice, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Papel (RBAC)", {"fields": ("role", "is_two_factor_enabled")}),
    )
    list_display = ("username", "email", "role", "is_two_factor_enabled", "is_staff")
    list_filter = ("role", "is_two_factor_enabled", "is_staff")


@admin.register(TwoFactorDevice)
class TwoFactorDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "method", "confirmed", "updated_at")
    list_filter = ("method", "confirmed")


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    list_display = ("user", "result", "ip_address", "created_at")
    list_filter = ("result",)
    readonly_fields = [f.name for f in LoginAttempt._meta.fields]
