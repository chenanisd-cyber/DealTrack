"""
Mise en ligne : en-têtes de sécurité, référencement (robots.txt, plan du
site), limite d'inscriptions, purge de la piste d'audit, cache des photos.
"""

import re
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import SuspiciousFileOperation
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation

from apps.accounts.models import User
from apps.deals.models import Deal, DealStatus
from apps.moderation.models import AuditLog
from config.ratelimit import allow
from config.site_views import media

from .factories import STRONG_PASSWORD, make_deal, make_user, seed_reference_data

TEMPLATES_DIR = settings.FRONTEND_DIR / "templates"


class SecurityHeadersTests(TestCase):
    def setUp(self):
        translation.activate("fr")
        self.addCleanup(translation.deactivate)

    def test_csp_sur_les_pages_et_sur_l_api(self):
        for url in (reverse("deals:list"), reverse("accounts:login"), "/api/v1/deals/"):
            csp = self.client.get(url)["Content-Security-Policy"]
            self.assertIn("default-src 'self'", csp)
            self.assertIn("script-src 'self'", csp)
            self.assertIn("frame-ancestors 'none'", csp)
            self.assertIn("object-src 'none'", csp)

    def test_csp_n_autorise_aucun_script_en_ligne(self):
        csp = self.client.get(reverse("deals:list"))["Content-Security-Policy"]
        script_src = next(d for d in csp.split("; ") if d.startswith("script-src"))
        self.assertEqual(script_src, "script-src 'self'")

    def test_autres_en_tetes(self):
        response = self.client.get(reverse("deals:list"))
        self.assertIn("camera=()", response["Permissions-Policy"])
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["Referrer-Policy"], "same-origin")

    def test_page_404_porte_aussi_la_csp(self):
        response = self.client.get("/fr/deal/inconnu/")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Content-Security-Policy", response)

    def test_gabarits_sans_script_en_ligne(self):
        """
        La CSP bloquerait ces scripts : un gabarit qui en ajoute casserait une
        fonction du site sans qu'aucun autre test ne le voie.
        """
        inline_script = re.compile(r"<script(?![^>]*\bsrc=)", re.IGNORECASE)
        handler = re.compile(r"\son[a-z]+\s*=\s*[\"']", re.IGNORECASE)
        for path in TEMPLATES_DIR.rglob("*.html"):
            source = path.read_text(encoding="utf-8")
            self.assertIsNone(inline_script.search(source), f"script en ligne : {path.name}")
            self.assertIsNone(handler.search(source), f"attribut on…= : {path.name}")
            self.assertNotIn("javascript:", source, path.name)

    def test_aucune_ressource_tierce_dans_la_page(self):
        """Police, CSS et JS viennent du site : rien n'est chargé chez un tiers."""
        html = self.client.get(reverse("deals:list")).content.decode()
        self.assertNotIn("fonts.googleapis.com", html)
        self.assertNotIn("fonts.gstatic.com", html)
        self.assertIn("fonts/jost-latin.woff2", html)


class SeoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        author = make_user("auteur@example.be", "Auteur")
        cls.published = make_deal(
            author, status=DealStatus.PUBLISHED, published_at=timezone.now()
        )
        cls.pending = make_deal(author, status=DealStatus.PENDING)

    def setUp(self):
        translation.activate("fr")
        self.addCleanup(translation.deactivate)

    def test_robots_txt(self):
        response = self.client.get("/robots.txt")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))
        body = response.content.decode()
        self.assertIn("Disallow: /api/", body)
        self.assertIn("Disallow: /*/back-office/", body)
        self.assertIn("Sitemap: http://testserver/sitemap.xml", body)

    def test_plan_du_site_ne_liste_que_les_offres_publiees(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn(f"/fr/deal/{self.published.slug}/", body)
        self.assertIn(f"/nl/deal/{self.published.slug}/", body)
        self.assertIn(f"/de/deal/{self.published.slug}/", body)
        self.assertNotIn(self.pending.slug, body)
        self.assertNotIn("back-office", body)

    def test_page_d_un_deal_decrite_pour_le_partage(self):
        html = self.client.get(self.published.get_absolute_url()).content.decode()
        self.assertIn('<link rel="canonical" href="http://testserver/fr/deal/', html)
        self.assertIn('property="og:title"', html)
        self.assertIn('hreflang="nl" href="http://testserver/nl/deal/', html)

    def test_premiere_photo_du_flux_prioritaire(self):
        """Une seule photo chargée en priorité ; les suivantes à l'approche de l'écran."""
        author = User.objects.get(email="auteur@example.be")
        for _ in range(3):
            make_deal(author, status=DealStatus.PUBLISHED, published_at=timezone.now())
        Deal.objects.update(image_url="https://images.example.be/photo.jpg")
        html = self.client.get(reverse("deals:list")).content.decode()
        self.assertEqual(html.count('fetchpriority="high"'), 1)
        self.assertGreaterEqual(html.count('loading="lazy"'), 2)


class RegistrationRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        translation.activate("fr")
        self.addCleanup(translation.deactivate)

    def post(self, email, ip="203.0.113.7"):
        return self.client.post(
            reverse("accounts:register"),
            {
                "email": email,
                "display_name": email.split("@")[0],
                "password1": "court",  # refusé : aucun compte n'est créé
                "password2": "court",
            },
            REMOTE_ADDR=ip,
        )

    @override_settings(REGISTER_RATE_LIMIT=3)
    def test_inscriptions_en_serie_bloquees(self):
        for n in range(3):
            self.assertEqual(self.post(f"robot{n}@example.be").status_code, 200)
        response = self.post("robot4@example.be")
        self.assertEqual(response.status_code, 429)
        self.assertContains(response, "Trop de tentatives", status_code=429)

    @override_settings(REGISTER_RATE_LIMIT=3)
    def test_la_limite_est_par_adresse(self):
        for n in range(4):
            self.post(f"robot{n}@example.be")
        self.assertEqual(self.post("autre@example.be", ip="198.51.100.9").status_code, 200)

    @override_settings(REGISTER_RATE_LIMIT=1)
    def test_un_compte_bloque_n_est_pas_cree(self):
        self.post("premier@example.be")
        response = self.client.post(
            reverse("accounts:register"),
            {
                "email": "second@example.be",
                "display_name": "Second",
                "preferred_language": "fr",
                "password1": STRONG_PASSWORD,
                "password2": STRONG_PASSWORD,
                "accept_terms": "on",
            },
            REMOTE_ADDR="203.0.113.7",
        )
        self.assertEqual(response.status_code, 429)
        self.assertFalse(User.objects.filter(email="second@example.be").exists())

    def test_compteur(self):
        self.assertTrue(allow("test-key", 2, 60))
        self.assertTrue(allow("test-key", 2, 60))
        self.assertFalse(allow("test-key", 2, 60))
        self.assertTrue(allow("autre-cle", 2, 60))


class AuditPurgeTests(TestCase):
    def make_entry(self, days_old):
        entry = AuditLog.record(action=AuditLog.Action.PERMISSION_DENIED)
        AuditLog.objects.filter(pk=entry.pk).update(
            created_at=timezone.now() - timedelta(days=days_old)
        )
        return entry

    def test_purge_les_entrees_trop_anciennes_seulement(self):
        old = self.make_entry(settings.AUDIT_LOG_RETENTION_DAYS + 1)
        recent = self.make_entry(settings.AUDIT_LOG_RETENTION_DAYS - 1)
        out = StringIO()
        call_command("purge_audit", stdout=out)
        self.assertFalse(AuditLog.objects.filter(pk=old.pk).exists())
        self.assertTrue(AuditLog.objects.filter(pk=recent.pk).exists())
        self.assertIn("1 entrée(s)", out.getvalue())

    def test_dry_run_ne_supprime_rien(self):
        old = self.make_entry(500)
        call_command("purge_audit", "--dry-run", stdout=StringIO())
        self.assertTrue(AuditLog.objects.filter(pk=old.pk).exists())


class MediaTests(TestCase):
    def test_photos_mises_en_cache_longtemps(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "deals").mkdir()
            (Path(folder) / "deals" / "photo.jpg").write_bytes(b"\xff\xd8\xff\xd9")
            with override_settings(MEDIA_ROOT=folder):
                request = RequestFactory().get("/media/deals/photo.jpg")
                response = media(request, "deals/photo.jpg")
                self.assertEqual(response.status_code, 200)
                self.assertIn("max-age=2592000", response["Cache-Control"])
                self.assertIn("immutable", response["Cache-Control"])
                response.close()
                # Un chemin qui sort du dossier des photos est refusé (réponse 400).
                with self.assertRaises(SuspiciousFileOperation):
                    media(request, "../manage.py")
