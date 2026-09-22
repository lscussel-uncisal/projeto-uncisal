from django.urls import path

from apps.tickets.views import (
    TicketCreateView,
    TicketDetailView,
    TicketListView,
    TicketUpdateView,
)

app_name = "tickets"

urlpatterns = [
    path("", TicketListView.as_view(), name="list"),
    path("novo/", TicketCreateView.as_view(), name="create"),
    path("<int:pk>/", TicketDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", TicketUpdateView.as_view(), name="update"),
]
