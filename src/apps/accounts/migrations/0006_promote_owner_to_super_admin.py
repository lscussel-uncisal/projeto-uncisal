from django.db import migrations

# Papel super-admin recém-criado (ver 0005_alter_user_role) — promove a conta do dono do
# projeto (mesma conta já usada em 0004_backfill_owner_display_name, e-mail não sensível,
# é a própria autoria do repositório). Nenhuma outra conta é tocada aqui.
OWNER_EMAIL = "leonardoscussel@gmail.com"


def promote_owner(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(username__iexact=OWNER_EMAIL).update(role="super_admin")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_alter_user_role"),
    ]

    operations = [
        migrations.RunPython(promote_owner, noop_reverse),
    ]
