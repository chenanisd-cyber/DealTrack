"""
Données existantes : premier point d'historique pour chaque offre (son prix
actuel, daté de sa publication) et alertes marquées comme déjà distribuées
pour les offres publiées avant l'arrivée du VIP.
"""

from django.db import migrations


def forwards(apps, schema_editor):
    Deal = apps.get_model("deals", "Deal")
    PricePoint = apps.get_model("deals", "PricePoint")
    points = []
    for deal in Deal.objects.all().iterator():
        if not PricePoint.objects.filter(deal_id=deal.pk).exists():
            points.append(
                PricePoint(
                    deal_id=deal.pk,
                    price=deal.price,
                    source="survey",
                    recorded_at=deal.published_at or deal.created_at,
                )
            )
    PricePoint.objects.bulk_create(points)
    for deal in Deal.objects.filter(status="published", alerts_dispatched_at__isnull=True):
        deal.alerts_dispatched_at = deal.published_at or deal.created_at
        deal.save(update_fields=["alerts_dispatched_at"])


class Migration(migrations.Migration):
    dependencies = [("deals", "0008_vip_price_alerts")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
