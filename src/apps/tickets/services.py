from django.db.models import QuerySet

from apps.accounts.models import Role, User
from apps.tickets.models import Status, Ticket


class TicketService:
    """Regras de negócio de chamados, isoladas da camada de views (SRP)."""

    @staticmethod
    def visible_to(user: User) -> QuerySet[Ticket]:
        """Admin e suporte veem todos os chamados; usuário comum ve apenas os que abriu."""
        if user.role in (Role.ADMIN, Role.SUPPORT):
            return Ticket.objects.all()
        return Ticket.objects.filter(requester=user)

    @staticmethod
    def can_edit(user: User, ticket: Ticket) -> bool:
        """Admin/suporte editam qualquer chamado, em qualquer status (triagem, atribuição,
        mudança de status). Usuário comum só edita o próprio chamado enquanto ele seguir
        'Aberto' — uma vez que o suporte começa a mexer (muda o status), só o suporte/admin
        edita dali pra frente, pra não haver edição concorrente de dois lados."""
        if user.role in (Role.ADMIN, Role.SUPPORT):
            return True
        return ticket.requester_id == user.id and ticket.status == Status.OPEN
