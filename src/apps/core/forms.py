from django import forms

# Classes reaproveitadas em todo input/select/textarea de texto — mantidas num só lugar pra
# não repetir a mesma string Tailwind em cada Form (DRY).
TEXT_INPUT_CLASSES = (
    "block w-full rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-900 "
    "shadow-sm placeholder:text-slate-400 focus:border-slate-500 focus:outline-none "
    "focus:ring-1 focus:ring-slate-500"
)
# Espaço extra à direita pro botão de mostrar/ocultar senha (ver templates/partials/form_fields.html)
# não ficar em cima do texto digitado. Escrita por extenso (não com TEXT_INPUT_CLASSES.replace(...))
# de propósito: o Tailwind é compilado a partir de um scan estático de texto no Dockerfile
# (ver docker/Dockerfile, estágio css-builder) — uma classe só nasce no CSS final se aparecer
# literalmente em algum arquivo que aquele estágio copia. "pl-3"/"pr-12" concatenados em runtime
# via .replace() já causaram um bug real: o botão de olho ficava sem padding em produção porque
# o scanner nunca via essas classes como texto.
PASSWORD_INPUT_CLASSES = (
    "block w-full rounded-md border border-slate-300 pl-3 pr-12 py-2 text-sm text-slate-900 "
    "shadow-sm placeholder:text-slate-400 focus:border-slate-500 focus:outline-none "
    "focus:ring-1 focus:ring-slate-500"
)
CHECKBOX_CLASSES = "h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-500"
RADIO_CLASSES = "h-4 w-4 border-slate-300 text-slate-900 focus:ring-slate-500"


class TailwindStyledFormMixin:
    """Aplica classes Tailwind a todo campo do formulario automaticamente, sem precisar
    estilizar widget por widget em cada Form nem depender de django-widget-tweaks — o
    `{{ form.as_p }}` puro do Django não carrega nenhum estilo, só o padrão (feio,
    inconsistente) do navegador. Usar em conjunto com `templates/partials/form_fields.html`."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", CHECKBOX_CLASSES)
            elif isinstance(widget, forms.RadioSelect):
                widget.attrs.setdefault("class", RADIO_CLASSES)
            elif isinstance(widget, forms.PasswordInput):
                widget.attrs.setdefault("class", PASSWORD_INPUT_CLASSES)
            else:
                widget.attrs.setdefault("class", TEXT_INPUT_CLASSES)
