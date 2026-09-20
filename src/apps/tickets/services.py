from django.db.models import QuerySet

from apps.accounts.models import Role, User
from apps.tickets.models import Ticket


class TicketService:
    """Regras de negócio de chamados, isoladas da camada de views (SRP)."""

    @staticmethod
    def visible_to(user: User) -> QuerySet[Ticket]:
        """Admin e suporte veem todos os chamados; usuário comum ve apenas os que abriu."""
        if user.role in (Role.ADMIN, Role.SUPPORT):
            return Ticket.objects.all()
        return Ticket.objects.filter(requester=user)
