from django.urls import path

from apps.tickets.views import TicketListView

app_name = "tickets"

urlpatterns = [
    path("", TicketListView.as_view(), name="list"),
]
