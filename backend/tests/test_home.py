"""
Page d'accueil : bannière saisonnière, onglets de tri, emplacements publicitaires.
"""

from datetime import date
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone, translation

from apps.deals.models import DealStatus
from apps.deals.season import season_banner

from .factories import make_deal, make_user, seed_reference_data


class SeasonBannerTests(TestCase):
    def test_black_november_puis_black_december(self):
        self.assertEqual(season_banner(date(2026, 11, 30))["title"], "Black November")
        self.assertEqual(season_banner(date(2026, 12, 1))["title"], "Black December")
        self.assertEqual(season_banner(date(2026, 12, 1))["year"], 2026)

    def test_aucune_banniere_le_reste_de_l_annee(self):
        for month in (1, 6, 10):
            self.assertIsNone(season_banner(date(2026, month, 15)))


class HomePageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        author = make_user("auteur@example.be", "Auteur")
        for _ in range(12):  # deux pages de flux
            make_deal(author, status=DealStatus.PUBLISHED, published_at=timezone.now())

    def setUp(self):
        # Un autre test peut laisser l'allemand actif : on fixe la langue de la page.
        translation.activate("fr")
        self.addCleanup(translation.deactivate)

    def get(self, url, day):
        with mock.patch("apps.deals.views.timezone.localdate", return_value=day):
            return self.client.get(url).content.decode()

    def test_banniere_selon_le_mois(self):
        url = reverse("deals:list")
        self.assertIn("Black November 2026", self.get(url, date(2026, 11, 8)))
        self.assertIn("Black December 2026", self.get(url, date(2026, 12, 2)))
        self.assertNotIn("Black ", self.get(url, date(2027, 2, 1)))

    def test_titre_selon_l_onglet(self):
        url = reverse("deals:list")
        self.assertIn("Offres populaires", self.get(url, date(2026, 11, 8)))
        self.assertIn("Nouveaux deals", self.get(url + "?tri=new", date(2026, 11, 8)))
        self.assertIn("Petits prix", self.get(url + "?tri=price", date(2026, 11, 8)))
        # Valeur inconnue : retour au tri par défaut, sans erreur.
        self.assertIn("Offres populaires", self.get(url + "?tri=zzz", date(2026, 11, 8)))

    def test_pagination_garde_le_tri(self):
        page = self.get(reverse("deals:list") + "?tri=new", date(2026, 11, 8))
        self.assertIn("?tri=new&amp;page=2", page)

    def test_deux_emplacements_publicitaires_sans_script_tiers(self):
        page = self.get(reverse("deals:list"), date(2026, 11, 8))
        self.assertEqual(page.count('class="ad__label"'), 2)
        self.assertNotIn("googlesyndication", page)
        self.assertNotIn("doubleclick", page)
