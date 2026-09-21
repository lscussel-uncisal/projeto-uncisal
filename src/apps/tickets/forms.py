from django import forms

from apps.accounts.models import Role, User
from apps.core.forms import TailwindStyledFormMixin
from apps.tickets.models import Ticket


class TicketCreateForm(TailwindStyledFormMixin, forms.ModelForm):
    """Abertura de chamado: requester nunca vem do form (é sempre request.user, setado na
    view) — só os campos que o próprio solicitante decide fazem sentido aqui."""

    class Meta:
        model = Ticket
        fields = ["title", "description", "priority"]


class TicketUserUpdateForm(TailwindStyledFormMixin, forms.ModelForm):
    """Edição pelo dono do chamado: só título/descrição. Status/prioridade/responsável são
    decisão do suporte, não do solicitante — ver TicketStaffUpdateForm."""

    class Meta:
        model = Ticket
        fields = ["title", "description"]


class TicketStaffUpdateForm(TailwindStyledFormMixin, forms.ModelForm):
    """Edição por admin/suporte: todos os campos, incluindo triagem (status, prioridade,
    responsável)."""

    class Meta:
        model = Ticket
        fields = ["title", "description", "status", "priority", "assignee"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # So pode atribuir chamado a quem de fato atende chamado (admin/suporte).
        self.fields["assignee"].queryset = User.objects.filter(role__in=[Role.ADMIN, Role.SUPPORT])
