"""
Démonstration chiffrée de la suppression logique.

Montre, en interrogeant la base à chaque étape :
  1. l'état initial d'un membre et de ses transactions,
  2. l'échec d'une suppression physique (ProtectedError levée par la contrainte),
  3. l'effet de soft_delete() : le compte disparaît des écrans, la ligne reste,
  4. l'effet de anonymise() : les données personnelles sont écrasées, la clé
     étrangère des factures reste valide.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, models, transaction

from apps.accounts.models import User
from apps.deals.models import Comment, Deal
from apps.payments.models import Payment, Subscription


class Command(BaseCommand):
    help = "Démontre le soft delete d'un membre ayant des transactions."

    def add_arguments(self, parser):
        parser.add_argument("--email", default="marc.vandenberghe@example.be")
        parser.add_argument(
            "--anonymise", action="store_true", help="Enchaîne sur l'anonymisation RGPD."
        )

    def handle(self, *args, **options):
        try:
            user = User.objects.get(email=options["email"])
        except User.DoesNotExist:
            # from None : le message est destiné à l'utilisateur en ligne de
            # commande, la trace de l'ORM ne lui apprendrait rien.
            raise CommandError(
                f"Compte introuvable : {options['email']}. Lancez d'abord seed_demo."
            ) from None

        self._section("1. État initial")
        self._snapshot(user)

        self._section("2. Tentative de suppression physique")
        try:
            with transaction.atomic():
                user.delete()
            self.stdout.write(
                self.style.ERROR(
                    "  La suppression a réussi : la contrainte PROTECT est absente."
                )
            )
        except models.ProtectedError as exc:
            protected = ", ".join(sorted({o.__class__.__name__ for o in exc.protected_objects}))
            self.stdout.write(
                self.style.SUCCESS(f"  ProtectedError levée. Objets protégés : {protected}")
            )
            self.stdout.write(
                "  C'est le comportement voulu : le droit comptable belge impose de\n"
                "  conserver les pièces justificatives sept ans (art. 315 CIR 92)."
            )

        self._section("3. Suppression logique")
        user.soft_delete(reason="Démonstration en ligne de commande", actor=user)
        user.refresh_from_db()
        self._snapshot(user)
        self._visibility(user)

        if options["anonymise"]:
            self._section("4. Anonymisation (droit à l'effacement)")
            before = {"email": user.email, "pseudo": user.display_name}
            user.anonymise(actor=user)
            user.refresh_from_db()
            self.stdout.write(f"  Avant : {before['email']} / {before['pseudo']}")
            self.stdout.write(f"  Après : {user.email} / {user.display_name}")
            self.stdout.write(f"  Mot de passe utilisable : {user.has_usable_password()}")
            self._snapshot(user)
            self.stdout.write(
                "\n  Les factures conservent la même clé étrangère : elles restent\n"
                "  rattachables à une entité comptable sans être nominatives."
            )

        self._section("Vérification SQL brute")
        self._raw_sql(user)

    # ------------------------------------------------------------------
    def _section(self, title):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"── {title} " + "─" * (56 - len(title))))

    def _snapshot(self, user):
        rows = [
            ("Identifiant (invariant)", str(user.pk)),
            ("E-mail", user.email),
            ("Pseudonyme", user.display_name),
            ("Actif", user.is_active),
            ("Désinscrit le", user.deleted_at or "—"),
            ("Anonymisé le", user.anonymised_at or "—"),
            ("Deals publiés", Deal.objects.filter(submitted_by=user).count()),
            ("Commentaires", Comment.objects.filter(author=user).count()),
            ("Paiements", Payment.objects.filter(user=user).count()),
            ("Abonnements", Subscription.objects.filter(user=user).count()),
        ]
        for label, value in rows:
            self.stdout.write(f"  {label:.<26} {value}")

    def _visibility(self, user):
        self.stdout.write("")
        self.stdout.write(
            f"  Visible par User.objects.active() ...... "
            f"{User.objects.active().filter(pk=user.pk).exists()}"
        )
        self.stdout.write(
            f"  Présent dans User.objects.all() ........ "
            f"{User.objects.filter(pk=user.pk).exists()}"
        )
        self.stdout.write(
            "  La ligne existe toujours ; seules les requêtes applicatives l'écartent."
        )

    def _raw_sql(self, user):
        # SQLite stocke un UUIDField en char(32) sans tirets, PostgreSQL en type
        # uuid natif. On délègue la conversion au backend plutôt que de coder en
        # dur un format, sinon la requête ne renvoie rien selon le moteur.
        pk_value = User._meta.pk.get_db_prep_value(user.pk, connection)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT email, display_name, is_active, deleted_at IS NOT NULL "
                "FROM accounts_user WHERE id = %s",
                [pk_value],
            )
            row = cursor.fetchone()
            self.stdout.write(f"  accounts_user   → {row}")

            cursor.execute(
                "SELECT reference, amount, status FROM payments_payment WHERE user_id = %s",
                [pk_value],
            )
            for line in cursor.fetchall():
                self.stdout.write(f"  payments_payment → {line}")

            cursor.execute(
                "SELECT COUNT(*) FROM payments_payment p "
                "LEFT JOIN accounts_user u ON u.id = p.user_id WHERE u.id IS NULL"
            )
            orphans = cursor.fetchone()[0]
            style = self.style.SUCCESS if orphans == 0 else self.style.ERROR
            self.stdout.write(style(f"  Factures orphelines : {orphans}"))
