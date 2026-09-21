from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.accounts.models import Role
from apps.tickets.forms import TicketCreateForm, TicketStaffUpdateForm, TicketUserUpdateForm
from apps.tickets.models import Ticket
from apps.tickets.services import TicketService


class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "tickets/ticket_list.html"
    context_object_name = "tickets"

    def get_queryset(self):
        return TicketService.visible_to(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["editable_ticket_ids"] = {
            ticket.pk for ticket in context["tickets"] if TicketService.can_edit(user, ticket)
        }
        return context


class TicketCreateView(LoginRequiredMixin, CreateView):
    model = Ticket
    form_class = TicketCreateForm
    template_name = "tickets/ticket_form.html"
    success_url = reverse_lazy("tickets:list")

    def form_valid(self, form):
        # requester e sempre quem esta logado — nunca um valor vindo do POST do cliente.
        form.instance.requester = self.request.user
        return super().form_valid(form)


class TicketUpdateView(LoginRequiredMixin, UpdateView):
    model = Ticket
    template_name = "tickets/ticket_form.html"
    success_url = reverse_lazy("tickets:list")

    def get_queryset(self):
        # Chamado que o usuario nem enxerga (visible_to) nunca aparece aqui — 404, nao 403.
        return TicketService.visible_to(self.request.user)

    def get_object(self, queryset=None):
        ticket = super().get_object(queryset)
        if not TicketService.can_edit(self.request.user, ticket):
            raise PermissionDenied
        return ticket

    def get_form_class(self):
        if self.request.user.role in (Role.ADMIN, Role.SUPPORT):
            return TicketStaffUpdateForm
        return TicketUserUpdateForm
