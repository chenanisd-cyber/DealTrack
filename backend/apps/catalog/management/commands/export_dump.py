"""
DUMP SQL de la base : structure ET données.

    python manage.py export_dump                       # → ../database/dump_dealtrack.sql
    python manage.py export_dump --output autre.sql
    python manage.py export_dump --counts              # nombre de lignes par table

Projet en « code first » : les tables viennent des modèles Django et de leurs
migrations, les données de seed_demo. Ce dump les fige dans un fichier SQL
que l'on peut relire, versionner ou recharger :

    sqlite3 nouvelle_base.sqlite3 < database/dump_dealtrack.sql

Contenu, pour chaque table : CREATE TABLE avec clé primaire, clés étrangères
(REFERENCES … DEFERRABLE INITIALLY DEFERRED), contraintes CHECK et UNIQUE ;
puis les CREATE INDEX ; puis les INSERT INTO. Seules les DONNÉES de
django_session sont exclues (jetons de connexion actifs, à ne jamais
publier) ; sa structure reste dans le dump.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.utils import timezone

# Données jamais exportées (la structure, elle, est conservée).
EXCLUDED_DATA = {"django_session"}

# Tables « naturellement limitées » au sens du cahier des charges : référentiels
# (3 régions belges, 6 catégories × 3 langues, 2 formules) et tables de liaison
# des droits du personnel (seuls admin et modérateurs y figurent).
NATURALLY_LIMITED = {
    "catalog_region",
    "catalog_category",
    "catalog_categorytranslation",
    "payments_plan",
    "accounts_user_groups",
    "accounts_user_user_permissions",
}
BUSINESS_PREFIXES = ("accounts_", "catalog_", "deals_", "payments_", "moderation_")


def table_counts():
    with connection.cursor() as cursor:
        tables = connection.introspection.table_names(cursor)
        counts = {}
        for table in tables:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')  # noqa: S608 — nom issu de l'introspection
            counts[table] = cursor.fetchone()[0]
    return counts


class Command(BaseCommand):
    help = "Exporte le DUMP SQL complet (structure + données) de la base."

    def add_arguments(self, parser):
        default = Path(settings.BASE_DIR).parent / "database" / "dump_dealtrack.sql"
        parser.add_argument("--output", default=str(default))
        parser.add_argument(
            "--counts", action="store_true", help="Affiche seulement le nombre de lignes."
        )

    def handle(self, *args, output, counts, **options):
        if connection.vendor != "sqlite":
            raise CommandError(
                "Base PostgreSQL : utilisez pg_dump, par exemple\n"
                "  pg_dump --no-owner --file=database/dump_dealtrack.sql $POSTGRES_DB"
            )

        rows = table_counts()
        business = {t: n for t, n in rows.items() if t.startswith(BUSINESS_PREFIXES)}
        too_small = [t for t, n in business.items() if n < 100 and t not in NATURALLY_LIMITED]
        if counts:
            for table, n in sorted(business.items()):
                flag = (
                    "limitée" if table in NATURALLY_LIMITED else ("OK" if n >= 100 else "< 100")
                )
                self.stdout.write(f"  {table:34} {n:6}  {flag}")
            return

        connection.ensure_connection()
        statements = [
            s
            for s in connection.connection.iterdump()
            if not any(s.startswith(f'INSERT INTO "{t}"') for t in EXCLUDED_DATA)
        ]
        # iterdump écrit chaque table suivie de ses données, par ordre
        # alphabétique : accounts_user (qui référence catalog_region) passerait
        # avant catalog_region. Ordre classique d'un dump : toutes les tables,
        # puis les données, puis les index. Les clés étrangères étant
        # DEFERRABLE INITIALLY DEFERRED, elles sont vérifiées au COMMIT.
        tables = [s for s in statements if s.startswith("CREATE TABLE")]
        indexes = [
            s for s in statements if s.startswith(("CREATE INDEX", "CREATE UNIQUE INDEX"))
        ]
        data = [
            s
            for s in statements
            if s not in tables
            and s not in indexes
            and s not in ("BEGIN TRANSACTION;", "COMMIT;")
        ]
        kept = [
            "BEGIN TRANSACTION;",
            "-- 1. Structure : tables, clés primaires et étrangères, contraintes",
            *tables,
            "-- 2. Données",
            *data,
            "-- 3. Index",
            *indexes,
            "COMMIT;",
        ]
        header = [
            "-- " + "=" * 74,
            "-- DealTrack.be — DUMP SQL complet (structure + données)",
            f"-- Généré le {timezone.localtime():%d/%m/%Y à %H:%M} par manage.py export_dump",
            "-- Moteur : SQLite (développement). Production : PostgreSQL (voir README).",
            "-- Approche « code first » : modèles Django → migrations → seed_demo → dump.",
            "-- Données de django_session exclues (jetons de connexion actifs).",
            "-- Mots de passe : hachés (Argon2), jamais en clair.",
            "--",
            "-- Nombre de lignes par table métier :",
            *[
                f"--   {table:34} {n:6}"
                + ("   (naturellement limitée)" if table in NATURALLY_LIMITED else "")
                for table, n in sorted(business.items())
            ],
            "-- " + "=" * 74,
            "PRAGMA foreign_keys = ON;",
            "",
        ]
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(header + kept) + "\n", encoding="utf-8")

        size = path.stat().st_size / 1024
        self.stdout.write(
            self.style.SUCCESS(
                f"Dump écrit : {path} ({size:,.0f} Ko, {len(rows)} tables, "
                f"{sum(1 for line in kept if line.startswith('INSERT'))} lignes de données)"
            )
        )
        if too_small:
            self.stdout.write(
                self.style.WARNING("Moins de 100 lignes : " + ", ".join(sorted(too_small)))
            )
