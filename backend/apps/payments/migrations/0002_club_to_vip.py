"""L'abonnement « Club » devient « VIP » : formules renommées sur place (paiements conservés)."""

from django.db import migrations

RENAMES = {
    "club-annuel": ("vip-annuel", "VIP annuel", "VIP jaarlijks", "VIP jährlich"),
    "club-mensuel": ("vip-mensuel", "VIP mensuel", "VIP maandelijks", "VIP monatlich"),
}


def forwards(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")
    for old, (code, fr, nl, de) in RENAMES.items():
        Plan.objects.filter(code=old).update(code=code, name_fr=fr, name_nl=nl, name_de=de)


def backwards(apps, schema_editor):
    Plan = apps.get_model("payments", "Plan")
    for old, (code, *_names) in RENAMES.items():
        Plan.objects.filter(code=code).update(code=old)


class Migration(migrations.Migration):
    dependencies = [("payments", "0001_initial")]

    operations = [migrations.RunPython(forwards, backwards)]
