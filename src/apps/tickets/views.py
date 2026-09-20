from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from apps.tickets.models import Ticket
from apps.tickets.services import TicketService


class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "tickets/ticket_list.html"
    context_object_name = "tickets"

    def get_queryset(self):
        return TicketService.visible_to(self.request.user)
