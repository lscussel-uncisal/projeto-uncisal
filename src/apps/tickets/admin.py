from django.contrib import admin

from apps.tickets.models import Ticket


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "status", "priority", "requester", "assignee", "created_at")
    list_filter = ("status", "priority")
    search_fields = ("title", "description")
