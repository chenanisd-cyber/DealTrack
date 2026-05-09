"""
Génère le dictionnaire de données à partir du schéma réel.

Écrire ce document à la main garantit qu'il diverge du code à la première
migration. En le dérivant de l'introspection Django, il reste exact par
construction : `python3 manage.py data_dictionary > docs/DATA_DICTIONARY.md`.
"""

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection, models

APP_ORDER = ["accounts", "catalog", "deals", "payments", "moderation"]

APP_TITLES = {
    "accounts": ("Comptes", "Membres, rôles et cycle de vie du compte."),
    "catalog": ("Catalogue", "Référentiels partagés : régions, catégories, marchands."),
    "deals": ("Offres", "Cœur métier : deals, votes, discussion, alertes."),
    "payments": ("Paiements", "Abonnement Club, transactions, pièces comptables."),
    "moderation": ("Modération et audit", "Piste d'audit, décisions, signalements."),
}

TYPE_LABELS = {
    "UUIDField": "UUID",
    "BigAutoField": "BIGINT auto",
    "AutoField": "INT auto",
    "CharField": "VARCHAR",
    "SlugField": "VARCHAR (slug)",
    "TextField": "TEXT",
    "EmailField": "VARCHAR (e-mail)",
    "URLField": "VARCHAR (URL)",
    "BooleanField": "BOOLEAN",
    "DateTimeField": "TIMESTAMP",
    "DecimalField": "DECIMAL",
    "IntegerField": "INT",
    "SmallIntegerField": "SMALLINT",
    "PositiveSmallIntegerField": "SMALLINT ≥ 0",
    "JSONField": "JSON",
    "GenericIPAddressField": "INET",
    "ForeignKey": "FK",
    "OneToOneField": "FK unique",
    "ManyToManyField": "M2M",
}


class Command(BaseCommand):
    help = "Produit le dictionnaire de données au format Markdown."

    def handle(self, *args, **options):
        out = self.stdout.write
        out("# Dictionnaire de données — DealTrack.be\n")
        out(
            "> Document généré depuis le schéma réel par "
            "`python3 manage.py data_dictionary`.\n"
            "> Il ne peut donc pas diverger des modèles.\n"
        )
        self._conventions(out)
        self._overview(out)

        for app_label in APP_ORDER:
            title, blurb = APP_TITLES[app_label]
            out(f"\n---\n\n## {title}\n")
            out(f"{blurb}\n")
            config = apps.get_app_config(app_label)
            for model in sorted(config.get_models(), key=lambda m: m._meta.db_table):
                self._model(model, out)

        self._integrity(out)

    # ------------------------------------------------------------------
    def _conventions(self, out):
        out("\n## Conventions\n")
        out("**Clés primaires.** Trois stratégies coexistent, chacune motivée :\n\n")
        out(
            "| Stratégie | Employée pour | Motif |\n"
            "|---|---|---|\n"
            "| `UUIDv4` | entités métier exposées par l'API | invariante, non "
            "énumérable, ne divulgue pas le volume de la base |\n"
            "| code naturel | `catalog_region` (NUTS-1) | référentiel officiel "
            "Eurostat, stable depuis 1988 ; une clé technique n'apporterait rien |\n"
            "| `BIGINT` auto | tables en ajout seul (`moderation_auditlog`, "
            "`deals_vote`) | l'ordre d'insertion porte du sens, l'identifiant n'est "
            "jamais exposé, et l'index conserve sa localité |\n"
        )
        out(
            "\n**Suppression.** Aucune entité rattachée à une transaction n'est "
            "supprimée physiquement. Les colonnes `deleted_at` portent la suppression "
            "logique ; `anonymised_at` marque l'effacement des données personnelles.\n"
        )
        out(
            "\n**Horodatage.** Toutes les colonnes temporelles sont en UTC "
            "(`USE_TZ = True`), converties à l'affichage vers `Europe/Brussels`.\n"
        )
        out(
            "\n**Montants.** `DECIMAL` et jamais `FLOAT` : un montant en virgule "
            "flottante introduit des écarts d'arrondi inacceptables sur une pièce "
            "comptable.\n"
        )

    def _overview(self, out):
        out("\n## Vue d'ensemble\n\n")
        out("| Table | Rôle | Clé primaire | Lignes en démo |\n|---|---|---|---|\n")
        for app_label in APP_ORDER:
            config = apps.get_app_config(app_label)
            for model in sorted(config.get_models(), key=lambda m: m._meta.db_table):
                meta = model._meta
                pk_type = TYPE_LABELS.get(
                    meta.pk.get_internal_type(), meta.pk.get_internal_type()
                )
                try:
                    count = model.objects.count()
                except Exception:
                    count = "—"
                out(
                    f"| `{meta.db_table}` | {meta.verbose_name_plural} | "
                    f"{meta.pk.name} · {pk_type} | {count} |\n"
                )

    def _model(self, model, out):
        meta = model._meta
        out(f"\n### `{meta.db_table}`\n")
        if model.__doc__:
            first = model.__doc__.strip().split("\n\n")[0]
            out(f"{' '.join(first.split())}\n")

        out(
            "\n| Colonne | Type | Null | Défaut | Contraintes et rôle |\n"
            "|---|---|---|---|---|\n"
        )
        for field in meta.fields:
            out(self._field_row(field))

        for field in meta.many_to_many:
            out(
                f"| `{field.name}` | M2M | — | — | table de liaison "
                f"`{field.remote_field.through._meta.db_table}` vers "
                f"`{field.related_model._meta.db_table}` |\n"
            )

        constraints = list(meta.constraints)
        if constraints:
            out("\n**Contraintes de table**\n")
            for constraint in constraints:
                out(f"- `{constraint.name}` — {self._describe(constraint)}\n")

        if meta.indexes:
            names = ", ".join(f"`{i.name}`" for i in meta.indexes)
            out(f"\n**Index** : {names}\n")

    def _field_row(self, field):
        internal = field.get_internal_type()
        type_label = TYPE_LABELS.get(internal, internal)

        if internal in {"CharField", "SlugField", "EmailField", "URLField"}:
            type_label += f"({field.max_length})"
        elif internal == "DecimalField":
            type_label += f"({field.max_digits},{field.decimal_places})"

        notes = []
        if field.primary_key:
            notes.append("**clé primaire**")
        if field.unique and not field.primary_key:
            notes.append("unique")
        if field.db_index and not field.primary_key and not field.unique:
            notes.append("indexée")

        if field.is_relation and field.many_to_one:
            target = field.related_model._meta.db_table
            on_delete = getattr(field.remote_field, "on_delete", None)
            behaviour = getattr(on_delete, "__name__", "—").upper()
            notes.append(f"→ `{target}` · `{behaviour}`")
            if behaviour == "PROTECT":
                notes.append("_bloque la suppression physique du parent_")

        if field.choices:
            values = ", ".join(f"`{c[0]}`" for c in field.choices[:6])
            notes.append(f"valeurs : {values}")

        help_text = str(field.help_text) if field.help_text else ""
        if help_text:
            notes.append(help_text)

        default = "—"
        if field.has_default():
            raw = field.default
            default = getattr(raw, "__name__", None) or str(raw)
            if default == "NOT_PROVIDED":
                default = "—"
            default = f"`{default[:24]}`"
        elif field.auto_created or internal in {"AutoField", "BigAutoField"}:
            default = "auto"

        return (
            f"| `{field.column}` | {type_label} | "
            f"{'oui' if field.null else 'non'} | {default} | "
            f"{' · '.join(notes) if notes else '—'} |\n"
        )

    def _describe(self, constraint):
        if isinstance(constraint, models.UniqueConstraint):
            return "unicité sur " + ", ".join(f"`{f}`" for f in constraint.fields)
        if isinstance(constraint, models.CheckConstraint):
            expression = getattr(constraint, "condition", None) or getattr(
                constraint, "check", None
            )
            return f"vérification : `{expression}`"
        return constraint.__class__.__name__

    def _integrity(self, out):
        out("\n---\n\n## Intégrité référentielle\n")
        out(
            "Le comportement de suppression est choisi champ par champ, "
            "jamais laissé par défaut.\n"
        )
        out("")
        out("| Relation | Comportement | Raison |\n|---|---|---|\n")
        rows = [
            (
                "`payments_payment.user_id` → `accounts_user`",
                "`PROTECT`",
                "verrou de conservation comptable : sept ans (art. 315 CIR 92). "
                "C'est cette contrainte qui rend la suppression logique obligatoire.",
            ),
            (
                "`deals_deal.submitted_by_id` → `accounts_user`",
                "`PROTECT`",
                "la modération doit pouvoir remonter à l'auteur d'une offre litigieuse",
            ),
            (
                "`deals_deal.merchant_id` → `catalog_merchant`",
                "`PROTECT`",
                "supprimer une enseigne effacerait son historique de prix",
            ),
            (
                "`deals_vote.deal_id` → `deals_deal`",
                "`CASCADE`",
                "un vote n'a aucun sens sans son offre ; l'offre n'est de toute façon "
                "jamais supprimée physiquement",
            ),
            (
                "`deals_comment.author_id` → `accounts_user`",
                "`PROTECT`",
                "les fils de discussion resteraient troués",
            ),
            (
                "`moderation_auditlog.actor_id` → `accounts_user`",
                "`SET_NULL`",
                "effacer un compte ne doit pas effacer la trace de ses actes, mais la "
                "trace ne doit pas non plus empêcher l'anonymisation ; `actor_label` "
                "conserve le pseudonyme figé",
            ),
            (
                "`catalog_categorytranslation.category_id` → `catalog_category`",
                "`CASCADE`",
                "un libellé n'existe pas sans sa catégorie",
            ),
        ]
        for relation, behaviour, reason in rows:
            out(f"| {relation} | {behaviour} | {reason} |\n")

        out("\n## Dénormalisation assumée\n")
        out(
            "`deals_deal.temperature` duplique une information dérivable de "
            "`deals_vote`. C'est délibéré : recalculer un `SUM` sur les votes pour "
            "chaque ligne du flux coûterait une agrégation par carte affichée. "
            "La table `Vote` reste souveraine et le compteur est recalculable à tout "
            "moment par `Deal.recompute_temperature()`, testé par "
            "`test_recompute_matches_vote_table`.\n"
        )
        out(
            "\n`moderation_auditlog.actor_label` duplique le pseudonyme au moment de "
            "l'action. Une piste d'audit doit rester lisible après l'anonymisation de "
            "l'auteur, ce qu'une simple jointure ne permettrait plus.\n"
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
                if connection.vendor == "sqlite"
                else "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = current_schema()"
            )
            out(
                f"\n---\n\n_Schéma : {cursor.fetchone()[0]} tables, "
                f"moteur `{connection.vendor}`._\n"
            )
