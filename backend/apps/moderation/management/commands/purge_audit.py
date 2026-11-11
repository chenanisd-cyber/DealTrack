"""
Purge de la piste d'audit au-delà de la durée de conservation.

Les entrées d'audit contiennent des adresses IP : ce sont des données
personnelles (RGPD), qu'on ne garde pas indéfiniment. La durée est fixée par
AUDIT_LOG_RETENTION_DAYS (365 jours). Lancée à chaque déploiement
(render-build.sh) ; peut aussi l'être par une tâche planifiée.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.moderation.models import AuditLog


class Command(BaseCommand):
    help = "Supprime les entrées d'audit plus anciennes que la durée de conservation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=settings.AUDIT_LOG_RETENTION_DAYS,
            help="Durée de conservation en jours (défaut : AUDIT_LOG_RETENTION_DAYS).",
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Compte sans rien supprimer."
        )

    def handle(self, *args, **options):
        limit = timezone.now() - timedelta(days=options["days"])
        old = AuditLog.objects.filter(created_at__lt=limit)
        if options["dry_run"]:
            self.stdout.write(f"{old.count()} entrée(s) d'audit à supprimer.")
            return
        deleted, _ = old.delete()
        self.stdout.write(f"{deleted} entrée(s) d'audit supprimée(s).")
