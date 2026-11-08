"""
DUMP SQL (manage.py export_dump) : structure + données, rechargeable tel quel.
"""

import sqlite3
import tempfile
from io import StringIO
from pathlib import Path

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.deals.models import DealStatus

from .factories import make_deal, make_user, seed_reference_data


class ExportDumpTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.member = make_user("membre@example.be", "Membre")
        make_deal(cls.member, status=DealStatus.PUBLISHED, published_at=timezone.now())

    def export(self):
        path = Path(tempfile.mkdtemp()) / "dump.sql"
        call_command("export_dump", output=str(path), stdout=StringIO())
        return path.read_text(encoding="utf-8")

    def test_structure_cles_contraintes_et_donnees(self):
        sql = self.export()
        self.assertIn('CREATE TABLE "deals_deal"', sql)
        self.assertIn("PRIMARY KEY", sql)
        self.assertIn('REFERENCES "catalog_merchant"', sql)  # clé étrangère
        self.assertIn("CHECK (", sql)  # contrainte d'intégrité
        self.assertIn("CREATE INDEX", sql)
        self.assertIn('INSERT INTO "deals_deal"', sql)
        # Les tables sont toutes créées avant la première ligne de données.
        self.assertLess(sql.rindex("CREATE TABLE"), sql.index("INSERT INTO"))

    def test_sessions_jamais_exportees(self):
        self.client.force_login(self.member)  # crée une ligne django_session
        sql = self.export()
        self.assertIn('CREATE TABLE "django_session"', sql)
        self.assertNotIn('INSERT INTO "django_session"', sql)

    def test_dump_rechargeable_sans_violation(self):
        db = sqlite3.connect(":memory:")
        db.executescript(self.export())
        self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
        self.assertEqual(db.execute("SELECT COUNT(*) FROM deals_deal").fetchone()[0], 1)

    def test_comptage_par_table(self):
        out = StringIO()
        call_command("export_dump", counts=True, stdout=out)
        self.assertIn("catalog_region", out.getvalue())
        self.assertIn("limitée", out.getvalue())
