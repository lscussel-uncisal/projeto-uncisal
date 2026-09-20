import pytest

from apps.accounts.models import Role, User
from apps.tickets.models import Ticket
from apps.tickets.services import TicketService


@pytest.mark.django_db
class TestTicketServiceVisibility:
    def test_regular_user_sees_only_own_tickets(self):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        other = User.objects.create_user(username="other", password="senha-forte-123")
        Ticket.objects.create(title="Meu chamado", description="...", requester=owner)
        Ticket.objects.create(title="Chamado de outro", description="...", requester=other)

        visible = TicketService.visible_to(owner)

        assert visible.count() == 1
        assert visible.first().requester == owner

    def test_support_sees_all_tickets(self):
        support = User.objects.create_user(
            username="suporte", password="senha-forte-123", role=Role.SUPPORT
        )
        user_a = User.objects.create_user(username="usera", password="senha-forte-123")
        user_b = User.objects.create_user(username="userb", password="senha-forte-123")
        Ticket.objects.create(title="A", description="...", requester=user_a)
        Ticket.objects.create(title="B", description="...", requester=user_b)

        assert TicketService.visible_to(support).count() == 2

    def test_admin_sees_all_tickets(self):
        admin = User.objects.create_user(
            username="admin", password="senha-forte-123", role=Role.ADMIN
        )
        user_a = User.objects.create_user(username="usera", password="senha-forte-123")
        Ticket.objects.create(title="A", description="...", requester=user_a)

        assert TicketService.visible_to(admin).count() == 1
