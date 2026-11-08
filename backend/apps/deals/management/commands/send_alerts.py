"""
Envoie par e-mail les alertes dont l'heure de disponibilité est passée.

    python manage.py send_alerts            # à planifier toutes les 5 minutes

Les correspondances sont créées à la publication d'un deal (apps/deals/vip.py) :
disponibles tout de suite pour un VIP, après le délai pour les autres. Cette
commande ne fait qu'envoyer celles qui sont arrivées à échéance, un e-mail
par membre, et les marque comme notifiées (jamais deux fois).
"""

from collections import defaultdict

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import override

from apps.deals.models import AlertMatch


class Command(BaseCommand):
    help = (
        "Envoie les alertes arrivées à échéance (VIP d'abord, autres membres après le délai)."
    )

    def handle(self, *args, **options):
        now = timezone.now()
        site = getattr(settings, "SITE_URL", "http://localhost:8000").rstrip("/")
        due = (
            AlertMatch.objects.filter(available_at__lte=now, notified_at__isnull=True)
            .select_related("alert__user", "deal", "deal__merchant")
            .order_by("-is_priority", "available_at")
        )
        by_user = defaultdict(list)
        for match in due:
            by_user[match.alert.user].append(match)

        sent = 0
        for user, matches in by_user.items():
            with override(user.preferred_language or "fr"):
                lines = [
                    f"- {m.deal.title_current} — {m.deal.price} € ({m.deal.merchant.name})\n"
                    f"  {site}{m.deal.get_absolute_url()}"
                    for m in matches
                ]
                subject = _("DealTrack : %(n)d deal(s) pour vos alertes") % {"n": len(matches)}
                body = "\n".join(
                    [_("Bonjour %(name)s,") % {"name": user.display_name}, "", *lines]
                )
            with transaction.atomic():
                send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [user.email])
                AlertMatch.objects.filter(pk__in=[m.pk for m in matches]).update(
                    notified_at=now
                )
                for match in matches:
                    match.alert.last_notified_at = now
                    match.alert.save(update_fields=["last_notified_at"])
            sent += 1
        self.stdout.write(self.style.SUCCESS(f"{sent} e-mail(s) d'alerte envoyé(s)."))
