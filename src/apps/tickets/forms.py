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


class StaffModelChoiceField(forms.ModelChoiceField):
    """Mostra o nome do agente (User.display_name), nunca o e-mail — e-mail é credencial,
    não dado pra expor a quem está sendo atendido."""

    def label_from_instance(self, obj: User) -> str:
        return obj.display_name


class TicketStaffUpdateForm(TailwindStyledFormMixin, forms.ModelForm):
    """Edição por admin/suporte: todos os campos, incluindo triagem (status, prioridade,
    responsável)."""

    assignee = StaffModelChoiceField(
        queryset=User.objects.none(), required=False, label="Responsável"
    )

    class Meta:
        model = Ticket
        fields = ["title", "description", "status", "priority", "assignee"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # So pode atribuir chamado a quem de fato atende chamado (super-admin/admin/suporte).
        self.fields["assignee"].queryset = User.objects.filter(
            role__in=[Role.SUPER_ADMIN, Role.ADMIN, Role.SUPPORT]
        )
