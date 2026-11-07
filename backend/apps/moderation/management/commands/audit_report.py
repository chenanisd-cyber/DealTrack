"""
Rapport d'audit d'activité.

Agrège la table AuditLog sur une fenêtre glissante et met en évidence les
signaux qui méritent un œil humain : échecs de connexion répétés depuis une
même adresse, refus d'accès en rafale, pics d'activité de modération.
"""

from collections import Counter
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from apps.moderation.models import AuditLog


class Command(BaseCommand):
    help = "Produit le rapport d'audit d'activité sur une période donnée."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--format", choices=["text", "csv"], default="text")

    def handle(self, *args, **options):
        since = timezone.now() - timedelta(days=options["days"])
        entries = AuditLog.objects.filter(created_at__gte=since)

        if options["format"] == "csv":
            return self._csv(entries)

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\nRapport d'audit — {options['days']} derniers jours "
                f"(depuis le {since:%d/%m/%Y})\n"
            )
        )

        total = entries.count()
        self.stdout.write(f"  Événements enregistrés : {total}\n")
        if not total:
            self.stdout.write("  Aucune activité sur la période.")
            return

        self.stdout.write(self.style.MIGRATE_HEADING("Répartition par action"))
        for row in entries.values("action").annotate(n=Count("id")).order_by("-n"):
            label = dict(AuditLog.Action.choices).get(row["action"], row["action"])
            self.stdout.write(f"  {label:.<44} {row['n']:>5}")

        self.stdout.write(self.style.MIGRATE_HEADING("\nMembres les plus actifs"))
        top = (
            entries.exclude(actor_label="")
            .values("actor_label")
            .annotate(n=Count("id"))
            .order_by("-n")[:8]
        )
        for row in top:
            self.stdout.write(f"  {row['actor_label']:.<44} {row['n']:>5}")

        # --- Signaux de sécurité ---
        self.stdout.write(self.style.MIGRATE_HEADING("\nSignaux à examiner"))
        flagged = False

        failures = Counter(
            entries.filter(action=AuditLog.Action.USER_LOGIN_FAILED)
            .exclude(ip_address=None)
            .values_list("ip_address", flat=True)
        )
        for ip, count in failures.most_common(5):
            if count >= 5:
                flagged = True
                self.stdout.write(
                    self.style.WARNING(f"  {count} échecs de connexion depuis {ip}")
                )

        denials = entries.filter(action=AuditLog.Action.PERMISSION_DENIED).count()
        if denials >= 10:
            flagged = True
            self.stdout.write(
                self.style.WARNING(
                    f"  {denials} refus d'accès : possible balayage d'identifiants."
                )
            )

        csrf = entries.filter(action=AuditLog.Action.CSRF_FAILURE).count()
        if csrf >= 5:
            flagged = True
            self.stdout.write(self.style.WARNING(f"  {csrf} échecs CSRF."))

        if not flagged:
            self.stdout.write(self.style.SUCCESS("  Rien d'anormal sur la période."))

        self.stdout.write(self.style.MIGRATE_HEADING("\nActivité RGPD"))
        for action in (
            AuditLog.Action.USER_DATA_EXPORTED,
            AuditLog.Action.USER_SOFT_DELETED,
            AuditLog.Action.USER_ANONYMISED,
        ):
            n = entries.filter(action=action).count()
            self.stdout.write(f"  {dict(AuditLog.Action.choices)[action]:.<44} {n:>5}")
        self.stdout.write("")

    def _csv(self, entries):
        import csv
        import sys

        writer = csv.writer(sys.stdout)
        writer.writerow(
            ["horodatage", "action", "auteur", "ip", "methode", "chemin", "details"]
        )
        for e in entries.order_by("created_at").iterator():
            writer.writerow(
                [
                    e.created_at.isoformat(),
                    e.action,
                    e.actor_label,
                    e.ip_address or "",
                    e.method,
                    e.path,
                    e.metadata,
                ]
            )
