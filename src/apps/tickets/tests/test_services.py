import pytest

from apps.accounts.models import Role, User
from apps.tickets.models import Status, Ticket
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


@pytest.mark.django_db
class TestTicketServiceCanEdit:
    def test_owner_can_edit_own_open_ticket(self):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        ticket = Ticket.objects.create(title="Meu chamado", description="...", requester=owner)

        assert TicketService.can_edit(owner, ticket) is True

    def test_owner_cannot_edit_own_ticket_once_no_longer_open(self):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        ticket = Ticket.objects.create(
            title="Meu chamado", description="...", requester=owner, status=Status.IN_PROGRESS
        )

        assert TicketService.can_edit(owner, ticket) is False

    def test_user_cannot_edit_someone_elses_ticket(self):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        other = User.objects.create_user(username="other", password="senha-forte-123")
        ticket = Ticket.objects.create(title="Chamado", description="...", requester=owner)

        assert TicketService.can_edit(other, ticket) is False

    def test_support_can_edit_any_ticket_regardless_of_status(self):
        support = User.objects.create_user(
            username="suporte", password="senha-forte-123", role=Role.SUPPORT
        )
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        ticket = Ticket.objects.create(
            title="Chamado", description="...", requester=owner, status=Status.CLOSED
        )

        assert TicketService.can_edit(support, ticket) is True

    def test_admin_can_edit_any_ticket(self):
        admin = User.objects.create_user(
            username="admin", password="senha-forte-123", role=Role.ADMIN
        )
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        ticket = Ticket.objects.create(title="Chamado", description="...", requester=owner)

        assert TicketService.can_edit(admin, ticket) is True
