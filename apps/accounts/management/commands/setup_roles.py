"""
Traduction des rôles applicatifs en droits Django.

Le champ `User.role` gouverne le front-office : `is_moderator` ouvre la file de
modération, l'API refuse `publish` à un membre. Le back-office, lui, ne connaît
pas ce champ. Il applique deux verrous successifs :

  1. `is_staff` autorise la connexion à /back-office/ ;
  2. une permission par modèle décide de ce qui apparaît dans l'index.

Sans le second, un modérateur franchit la porte et tombe sur une page vide :
« Vous n'avez la permission de modifier aucun objet. » Le rôle est correct en
base, l'écran est inutilisable. Cette commande pose le chaînon manquant en
rattachant les modérateurs à un groupe porteur des permissions utiles.

Le groupe est préféré à des permissions individuelles : un droit ajouté ici
profite à tous les modérateurs, présents et futurs, sans repasser sur chaque
compte. Les administrateurs, eux, reçoivent `is_superuser` : Django court-circuite
alors la vérification des permissions, le groupe leur serait sans effet.

Idempotente : la relancer après chaque déploiement est sans risque, et c'est
l'usage prévu — un nouveau modèle apporte de nouvelles permissions.
"""

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, User

MODERATOR_GROUP = "Modérateurs"

# Permissions du groupe, groupées par application pour rester lisibles et pour
# lever l'ambiguïté d'un codename : `view_user` n'existe qu'ici, mais rien ne
# garantit qu'une application future n'introduise pas un homonyme.
MODERATOR_PERMISSIONS = {
    # Le cœur du métier : valider, corriger, retirer une offre et ses réactions.
    "deals": [
        "view_deal",
        "change_deal",
        "view_comment",
        "change_comment",
        "view_vote",
        "view_alert",
    ],
    # Traiter les signalements et tracer chaque décision. `view_auditlog` sans
    # add/change/delete : la piste d'audit se consulte, elle ne se retouche pas
    # (AuditLogAdmin refuse les trois autres verbes).
    "moderation": [
        "view_report",
        "change_report",
        "view_moderationdecision",
        "add_moderationdecision",
        "view_auditlog",
    ],
    # Un marchand inconnu apparaît avec la première offre qui le cite : le
    # modérateur doit pouvoir le créer et le vérifier sans appeler un admin.
    # Catégories et régions restent en lecture seule, ce sont des référentiels.
    "catalog": [
        "view_merchant",
        "change_merchant",
        "add_merchant",
        "view_category",
        "view_region",
    ],
    # Lecture seule : identifier l'auteur d'une offre litigieuse, vérifier
    # qu'un compte signalé est bien abonné. Aucune écriture — ni sur les
    # comptes, ni sur les paiements, qui relèvent de la comptabilité.
    "accounts": ["view_user"],
    "payments": ["view_payment", "view_subscription"],
}


class Command(BaseCommand):
    help = (
        "Crée le groupe « Modérateurs », lui attribue ses permissions et y "
        "rattache les comptes selon leur rôle. Idempotente."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche ce qui serait fait sans rien écrire en base.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        permissions = self._resolve_permissions()
        group, created = Group.objects.get_or_create(name=MODERATOR_GROUP)

        self._section("Groupe")
        verb = "créé" if created else "déjà présent"
        self.stdout.write(f"  « {MODERATOR_GROUP} » {verb}.")

        before = set(group.permissions.values_list("pk", flat=True))
        wanted = {p.pk for p in permissions}
        added, removed = wanted - before, before - wanted

        if not dry_run:
            # set() plutôt que add() : le groupe converge vers la liste ci-dessus
            # au lieu d'accumuler des droits retirés du code depuis longtemps.
            group.permissions.set(permissions)

        self.stdout.write(f"  Permissions visées ..... {len(wanted)}")
        self.stdout.write(f"  Ajoutées ............... {len(added)}")
        self.stdout.write(f"  Retirées ............... {len(removed)}")
        newly_granted = sorted(
            f"{p.content_type.app_label}.{p.codename}" for p in permissions if p.pk in added
        )
        for label in newly_granted:
            self.stdout.write(f"    + {label}")

        # -- Modérateurs -------------------------------------------------
        self._section("Modérateurs")
        moderators = User.objects.filter(role=Role.MODERATOR)
        in_group = set(group.user_set.values_list("pk", flat=True))
        to_attach = [u for u in moderators if u.pk not in in_group]
        to_staff = [u for u in moderators if not u.is_staff]

        if not dry_run:
            if to_attach:
                group.user_set.add(*to_attach)
            if to_staff:
                User.objects.filter(pk__in=[u.pk for u in to_staff]).update(is_staff=True)

        self.stdout.write(f"  Comptes de rôle modérateur ... {moderators.count()}")
        self.stdout.write(f"  Rattachés au groupe .......... {len(to_attach)}")
        self.stdout.write(f"  Passés is_staff=True ......... {len(to_staff)}")
        for user in to_attach or to_staff:
            self.stdout.write(f"    · {user.email}")

        # -- Administrateurs ---------------------------------------------
        self._section("Administrateurs")
        admins = User.objects.filter(role=Role.ADMIN)
        to_promote = [u for u in admins if not (u.is_staff and u.is_superuser)]

        if not dry_run and to_promote:
            User.objects.filter(pk__in=[u.pk for u in to_promote]).update(
                is_staff=True, is_superuser=True
            )

        self.stdout.write(f"  Comptes de rôle administrateur ... {admins.count()}")
        self.stdout.write(f"  Promus staff + superuser ......... {len(to_promote)}")
        for user in to_promote:
            self.stdout.write(f"    · {user.email}")

        self.stdout.write("")
        if dry_run:
            self.stdout.write(self.style.WARNING("Simulation : aucune écriture effectuée."))
            # La transaction est annulée explicitement plutôt que laissée
            # committer les get_or_create faits en chemin.
            transaction.set_rollback(True)
        else:
            self.stdout.write(self.style.SUCCESS("Rôles synchronisés."))

    # ------------------------------------------------------------------
    def _resolve_permissions(self):
        """
        Résout les codenames en objets Permission.

        Un codename absent signale soit une faute de frappe, soit un `migrate`
        qui n'a pas tourné : les permissions sont créées par le signal
        post_migrate, pas par le schéma. Mieux vaut s'arrêter net que produire
        un groupe silencieusement amputé.
        """
        resolved, missing = [], []
        for app_label, codenames in MODERATOR_PERMISSIONS.items():
            found = Permission.objects.filter(
                content_type__app_label=app_label, codename__in=codenames
            ).select_related("content_type")
            by_codename = {p.codename: p for p in found}
            for codename in codenames:
                if codename in by_codename:
                    resolved.append(by_codename[codename])
                else:
                    missing.append(f"{app_label}.{codename}")

        if missing:
            raise CommandError(
                "Permissions introuvables : "
                + ", ".join(missing)
                + ". Lancez d'abord « manage.py migrate »."
            )
        return resolved

    def _section(self, title):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(f"── {title} " + "─" * (56 - len(title))))
