import pytest
from django.urls import reverse

from apps.accounts.models import Role, User
from apps.tickets.models import Priority, Status, Ticket


@pytest.mark.django_db
class TestTicketListView:
    def test_requires_login(self, client):
        response = client.get(reverse("tickets:list"))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_regular_user_only_sees_own_tickets(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        other = User.objects.create_user(username="other", password="senha-forte-123")
        mine = Ticket.objects.create(title="Meu chamado", description="...", requester=owner)
        Ticket.objects.create(title="De outro usuário", description="...", requester=other)
        client.force_login(owner)

        response = client.get(reverse("tickets:list"))

        tickets = list(response.context["tickets"])
        assert tickets == [mine]

    def test_support_sees_every_ticket(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        support = User.objects.create_user(
            username="suporte", password="senha-forte-123", role=Role.SUPPORT
        )
        Ticket.objects.create(title="Chamado 1", description="...", requester=owner)
        Ticket.objects.create(title="Chamado 2", description="...", requester=owner)
        client.force_login(support)

        response = client.get(reverse("tickets:list"))

        assert len(response.context["tickets"]) == 2

    def test_list_is_paginated(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        client.force_login(owner)
        for i in range(25):
            Ticket.objects.create(title=f"Chamado {i}", description="...", requester=owner)

        response = client.get(reverse("tickets:list"))

        assert response.context["is_paginated"] is True
        assert len(response.context["tickets"]) == 20

    def test_filter_by_status(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        client.force_login(owner)
        open_ticket = Ticket.objects.create(
            title="Aberto", description="...", requester=owner, status=Status.OPEN
        )
        Ticket.objects.create(
            title="Resolvido", description="...", requester=owner, status=Status.RESOLVED
        )

        response = client.get(reverse("tickets:list"), {"status": Status.OPEN})

        assert list(response.context["tickets"]) == [open_ticket]

    def test_filter_by_date_range(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        client.force_login(owner)
        in_range = Ticket.objects.create(title="Dentro", description="...", requester=owner)
        Ticket.objects.filter(pk=in_range.pk).update(created_at="2020-01-15T12:00:00Z")
        out_of_range = Ticket.objects.create(title="Fora", description="...", requester=owner)
        Ticket.objects.filter(pk=out_of_range.pk).update(created_at="2021-06-01T12:00:00Z")

        response = client.get(
            reverse("tickets:list"), {"date_from": "2020-01-01", "date_to": "2020-01-31"}
        )

        assert list(response.context["tickets"]) == [in_range]


@pytest.mark.django_db
class TestTicketDetailView:
    def test_requires_login(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        ticket = Ticket.objects.create(title="Original", description="...", requester=owner)

        response = client.get(reverse("tickets:detail", args=[ticket.pk]))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_owner_can_view_own_ticket_even_when_not_editable(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        ticket = Ticket.objects.create(
            title="Original",
            description="Detalhes do problema",
            requester=owner,
            status=Status.IN_PROGRESS,
            priority=Priority.HIGH,
        )
        client.force_login(owner)

        response = client.get(reverse("tickets:detail", args=[ticket.pk]))

        assert response.status_code == 200
        assert "Detalhes do problema" in response.content.decode()

    def test_user_cannot_view_someone_elses_ticket(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        other = User.objects.create_user(username="other", password="senha-forte-123")
        ticket = Ticket.objects.create(title="Original", description="...", requester=owner)
        client.force_login(other)

        response = client.get(reverse("tickets:detail", args=[ticket.pk]))

        assert response.status_code == 404

    def test_support_can_view_any_ticket(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        support = User.objects.create_user(
            username="suporte", password="senha-forte-123", role=Role.SUPPORT
        )
        ticket = Ticket.objects.create(title="Original", description="...", requester=owner)
        client.force_login(support)

        response = client.get(reverse("tickets:detail", args=[ticket.pk]))

        assert response.status_code == 200

    def test_shows_assignee_name_never_email(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        support = User.objects.create_user(
            username="suporte@example.com",
            password="senha-forte-123",
            role=Role.SUPPORT,
            first_name="Maria",
            last_name="Souza",
        )
        ticket = Ticket.objects.create(
            title="Original", description="...", requester=owner, assignee=support
        )
        client.force_login(owner)

        response = client.get(reverse("tickets:detail", args=[ticket.pk]))

        content = response.content.decode()
        assert "suporte@example.com" not in content
        assert "Maria Souza" in content


@pytest.mark.django_db
class TestTicketCreateView:
    def test_requires_login(self, client):
        response = client.get(reverse("tickets:create"))

        assert response.status_code == 302
        assert reverse("accounts:login") in response.url

    def test_creates_a_ticket_with_the_logged_in_user_as_requester(self, client):
        user = User.objects.create_user(username="joao", password="senha-forte-123")
        client.force_login(user)

        response = client.post(
            reverse("tickets:create"),
            {"title": "Impressora não funciona", "description": "Não liga.", "priority": "high"},
        )

        assert response.status_code == 302
        ticket = Ticket.objects.get()
        assert ticket.requester == user
        assert ticket.title == "Impressora não funciona"
        assert ticket.status == Status.OPEN

    def test_cannot_set_requester_or_status_via_client_data(self, client):
        user = User.objects.create_user(username="joao", password="senha-forte-123")
        other = User.objects.create_user(username="other", password="senha-forte-123")
        client.force_login(user)

        client.post(
            reverse("tickets:create"),
            {
                "title": "Tentando forjar",
                "description": "...",
                "priority": "low",
                "requester": other.pk,
                "status": Status.CLOSED,
            },
        )

        ticket = Ticket.objects.get()
        assert ticket.requester == user
        assert ticket.status == Status.OPEN


@pytest.mark.django_db
class TestTicketUpdateView:
    def test_owner_can_edit_own_open_ticket(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        ticket = Ticket.objects.create(title="Original", description="...", requester=owner)
        client.force_login(owner)

        response = client.post(
            reverse("tickets:update", args=[ticket.pk]),
            {"title": "Editado pelo dono", "description": "Atualizado."},
        )

        assert response.status_code == 302
        ticket.refresh_from_db()
        assert ticket.title == "Editado pelo dono"

    def test_owner_cannot_change_status_or_assignee(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        support = User.objects.create_user(
            username="suporte", password="senha-forte-123", role=Role.SUPPORT
        )
        ticket = Ticket.objects.create(title="Original", description="...", requester=owner)
        client.force_login(owner)

        client.post(
            reverse("tickets:update", args=[ticket.pk]),
            {
                "title": "Editado",
                "description": "...",
                "status": Status.CLOSED,
                "assignee": support.pk,
            },
        )

        ticket.refresh_from_db()
        assert ticket.status == Status.OPEN
        assert ticket.assignee is None

    def test_owner_cannot_edit_ticket_once_no_longer_open(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        ticket = Ticket.objects.create(
            title="Original", description="...", requester=owner, status=Status.IN_PROGRESS
        )
        client.force_login(owner)

        response = client.post(
            reverse("tickets:update", args=[ticket.pk]),
            {"title": "Tentando editar", "description": "..."},
        )

        assert response.status_code == 403
        ticket.refresh_from_db()
        assert ticket.title == "Original"

    def test_user_cannot_edit_someone_elses_ticket(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        other = User.objects.create_user(username="other", password="senha-forte-123")
        ticket = Ticket.objects.create(title="Original", description="...", requester=owner)
        client.force_login(other)

        response = client.get(reverse("tickets:update", args=[ticket.pk]))

        assert response.status_code == 404

    def test_support_can_change_status_and_assignee_on_any_ticket(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        support = User.objects.create_user(
            username="suporte", password="senha-forte-123", role=Role.SUPPORT
        )
        ticket = Ticket.objects.create(title="Original", description="...", requester=owner)
        client.force_login(support)

        response = client.post(
            reverse("tickets:update", args=[ticket.pk]),
            {
                "title": "Original",
                "description": "...",
                "status": Status.IN_PROGRESS,
                "priority": "high",
                "assignee": support.pk,
            },
        )

        assert response.status_code == 302
        ticket.refresh_from_db()
        assert ticket.status == Status.IN_PROGRESS
        assert ticket.assignee == support

    def test_support_can_edit_even_a_closed_ticket(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        support = User.objects.create_user(
            username="suporte", password="senha-forte-123", role=Role.SUPPORT
        )
        ticket = Ticket.objects.create(
            title="Original", description="...", requester=owner, status=Status.CLOSED
        )
        client.force_login(support)

        response = client.post(
            reverse("tickets:update", args=[ticket.pk]),
            {
                "title": "Reaberto pelo suporte",
                "description": "...",
                "status": Status.OPEN,
                "priority": "medium",
            },
        )

        assert response.status_code == 302
        ticket.refresh_from_db()
        assert ticket.title == "Reaberto pelo suporte"

    def test_assignee_choices_are_restricted_to_staff(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        support = User.objects.create_user(
            username="suporte", password="senha-forte-123", role=Role.SUPPORT
        )
        regular = User.objects.create_user(username="regular", password="senha-forte-123")
        ticket = Ticket.objects.create(title="Original", description="...", requester=owner)
        client.force_login(support)

        response = client.get(reverse("tickets:update", args=[ticket.pk]))

        assignee_field = response.context["form"].fields["assignee"]
        choices = list(assignee_field.queryset)
        assert support in choices
        assert regular not in choices

    def test_assignee_dropdown_shows_name_never_email(self, client):
        owner = User.objects.create_user(username="owner", password="senha-forte-123")
        support = User.objects.create_user(
            username="suporte@example.com",
            password="senha-forte-123",
            role=Role.SUPPORT,
            first_name="Maria",
            last_name="Souza",
        )
        ticket = Ticket.objects.create(title="Original", description="...", requester=owner)
        client.force_login(support)

        response = client.get(reverse("tickets:update", args=[ticket.pk]))

        assert "suporte@example.com" not in response.content.decode()
        assert "Maria Souza" in response.content.decode()
