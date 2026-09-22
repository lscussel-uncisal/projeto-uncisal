from django.db import migrations

# Backfill do nome/sobrenome da conta do dono do projeto, pra que o campo "Responsável" em
# chamados (e qualquer outro lugar que use User.display_name) mostre um nome de verdade em
# vez de cair no fallback (identificador local do e-mail). Não toca em nenhuma outra conta —
# cada usuário/administrador preenche o próprio nome em "Informações pessoais" no admin.
OWNER_EMAIL = "leonardoscussel@gmail.com"
OWNER_FIRST_NAME = "Leonardo"
OWNER_LAST_NAME = "Scussel"


def backfill_owner_name(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(username__iexact=OWNER_EMAIL, first_name="", last_name="").update(
        first_name=OWNER_FIRST_NAME, last_name=OWNER_LAST_NAME
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_alter_loginattempt_result"),
    ]

    operations = [
        migrations.RunPython(backfill_owner_name, noop_reverse),
    ]
