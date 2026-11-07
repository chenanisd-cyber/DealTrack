"""
Fonctionnalités « vivantes » : lecture du prix depuis un lien, reconnaissance
du marchand, vote sans rechargement, annuaire des commerçants locaux et
protection du back-office en mode partage.
"""

from decimal import Decimal

from bs4 import BeautifulSoup
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.catalog.models import Merchant
from apps.deals.models import DealStatus
from apps.deals.scraper import LOWEST_30_DAYS, _json_ld_products, parse_price
from apps.deals.views import match_merchant
from config.share_middleware import PublicBackOfficeBlockMiddleware

from .factories import make_deal, make_user, seed_reference_data


class PriceParsingTests(TestCase):
    def test_formats_belges_et_internationaux(self):
        cases = {
            "1.229,00 €": "1229.00",
            "€ 399,-": "399.00",
            "502,60€": "502.60",
            "399.00": "399.00",
            "€ 1.199,-": "1199.00",
            "2,99": "2.99",
            "1,229.00": "1229.00",
        }
        for raw, expected in cases.items():
            self.assertEqual(parse_price(raw), Decimal(expected), raw)

    def test_valeurs_absurdes_ignorees(self):
        for raw in (None, "", "gratuit", "0", "-5"):
            self.assertIsNone(parse_price(raw), raw)

    def test_donnees_structurees_json_ld(self):
        html = (
            '<script type="application/ld+json">{"@context":"https://schema.org",'
            '"@graph":[{"@type":"Product","name":"Casque","offers":{"price":"79.95"}}]}'
            "</script>"
        )
        product = next(_json_ld_products(BeautifulSoup(html, "html.parser")))
        self.assertEqual(product["offers"]["price"], "79.95")

    def test_prix_de_reference_legal_reconnu(self):
        text = "Prix le plus bas des 30 derniers jours : 502,60€"
        self.assertEqual(parse_price(LOWEST_30_DAYS.search(text).group(1)), Decimal("502.60"))


class MerchantMatchingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.amazon = Merchant.objects.create(
            name="Amazon.com.be",
            slug="amazon-com-be",
            country="LU",
            website="https://www.amazon.com.be",
        )

    def test_domaine_et_sous_domaine(self):
        self.assertEqual(match_merchant("https://www.amazon.com.be/dp/B0DY8V59LY"), self.amazon)
        self.assertEqual(match_merchant("https://smile.amazon.com.be/x"), self.amazon)

    def test_domaine_piege_refuse(self):
        self.assertIsNone(match_merchant("https://amazon.com.be.example.org/dp/x"))
        self.assertIsNone(match_merchant("https://www.notamazon.com.be/"))


class LiveVoteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.author = make_user("auteur@example.be", "Auteur")
        cls.voter = make_user("votant@example.be", "Votant")
        cls.deal = make_deal(
            cls.author,
            status=DealStatus.PUBLISHED,
            published_at=timezone.now(),
            temperature=100,
        )

    def test_vote_en_direct_renvoie_temperature_et_etat(self):
        self.client.force_login(self.voter)
        url = reverse("deals:vote", args=[self.deal.slug])
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        first = self.client.post(url, {"value": "1"}, **headers).json()
        self.assertEqual(first, {"temperature": 101, "user_vote": 1})
        again = self.client.post(url, {"value": "1"}, **headers).json()  # annule le vote
        self.assertEqual(again, {"temperature": 100, "user_vote": 0})

    def test_badges_nouveau_et_brulant(self):
        self.deal.temperature = 650
        self.assertTrue(self.deal.is_hot)
        self.assertTrue(self.deal.is_new)


class LocalMerchantsPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Merchant.objects.create(
            name="Hinkelspel",
            slug="hinkelspel",
            shop_type="cheese",
            city="Gent",
            is_local_independent=True,
            osm_id=2225073582,
        )
        Merchant.objects.create(
            name="Tropismes",
            slug="tropismes",
            shop_type="books",
            city="Bruxelles",
            is_local_independent=True,
        )

    def test_annuaire_et_filtre_par_ville(self):
        html = self.client.get(reverse("deals:local")).content.decode()
        self.assertIn("Hinkelspel", html)
        self.assertIn("Tropismes", html)
        self.assertIn("openstreetmap.org/copyright", html)  # attribution ODbL
        self.assertEqual(html.count("?ville=Gent"), 1)  # une seule puce par ville
        gent = self.client.get(reverse("deals:local"), {"ville": "Gent"}).content.decode()
        self.assertIn("Hinkelspel", gent)
        self.assertNotIn("Tropismes", gent)

    def test_ville_inconnue_ignoree(self):
        response = self.client.get(reverse("deals:local"), {"ville": "' OR 1=1--"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("Tropismes", response.content.decode())


@override_settings(ALLOWED_HOSTS=[".trycloudflare.com", "localhost", "testserver"])
class ShareModeTests(TestCase):
    def setUp(self):
        self.middleware = PublicBackOfficeBlockMiddleware(lambda request: HttpResponse("ok"))
        self.factory = RequestFactory()

    def test_back_office_ferme_depuis_internet(self):
        from django.http import Http404

        request = self.factory.get("/fr/back-office/", HTTP_HOST="abc.trycloudflare.com")
        with self.assertRaises(Http404):
            self.middleware(request)
        request = self.factory.get(
            "/fr/back-office/", HTTP_HOST="localhost", HTTP_CF_CONNECTING_IP="203.0.113.7"
        )
        with self.assertRaises(Http404):
            self.middleware(request)

    def test_back_office_ouvert_en_local_et_site_public(self):
        local = self.factory.get("/fr/back-office/", HTTP_HOST="localhost")
        self.assertEqual(self.middleware(local).status_code, 200)
        public_page = self.factory.get("/fr/", HTTP_HOST="abc.trycloudflare.com")
        self.assertEqual(self.middleware(public_page).status_code, 200)


class SubmissionWizardTests(TestCase):
    """Publication façon site de deals : marchand automatique, galerie, magasin."""

    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.member = make_user("membre@example.be", "Membre")

    def setUp(self):
        self.client.force_login(self.member)

    def post(self, **overrides):
        from apps.catalog.models import Category

        data = {
            "title": "Nintendo Switch 2 avec Mario Kart World",
            "description": "Pack console et jeu, livraison depuis les Pays-Bas en trois jours.",
            "external_url": "https://www.joybuy.nl/switch-2",
            "price": "448.90",
            "availability": "online",
            "shipping_cost": "0.00",
            "category": Category.objects.filter(is_active=True).first().pk,
            "language": "fr",
        }
        data.update(overrides)
        return self.client.post(reverse("deals:submit"), data)

    def test_marchand_cree_d_apres_le_domaine(self):
        from apps.deals.models import Deal

        response = self.post(promo_code=" SWITCH10 ")
        self.assertEqual(response.status_code, 302, response.content.decode()[:300])
        deal = Deal.objects.get(external_url="https://www.joybuy.nl/switch-2")
        self.assertEqual(deal.merchant.name, "Joybuy")
        self.assertEqual(deal.merchant.country, "NL")
        self.assertFalse(deal.merchant.is_verified)
        self.assertTrue(deal.is_cross_border)  # hors Belgique : automatique
        self.assertEqual(deal.promo_code, "SWITCH10")
        self.assertEqual(deal.regions.count(), 3)  # aucune case : toute la Belgique

    def test_deuxieme_deal_reutilise_le_meme_marchand(self):
        self.post()
        self.post(
            external_url="https://joybuy.nl/autre", title="Manette Pro Nintendo Switch 2 noire"
        )
        self.assertEqual(Merchant.objects.filter(name="Joybuy").count(), 1)

    def test_deal_en_magasin_sans_lien(self):
        from apps.deals.models import Deal

        response = self.post(
            external_url="", availability="in_store", merchant_name="Fromagerie du Coin"
        )
        self.assertEqual(response.status_code, 302, response.content.decode()[:300])
        deal = Deal.objects.get(title__startswith="Nintendo")
        self.assertEqual(deal.merchant.name, "Fromagerie du Coin")
        self.assertFalse(deal.is_cross_border)

    def test_deal_en_ligne_exige_un_lien(self):
        response = self.post(external_url="")
        self.assertTrue(response.context["form"].has_error("external_url"))

    def test_huit_images_au_maximum(self):
        import json

        urls = [f"https://cdn.joybuy.nl/{i}.jpg" for i in range(9)]
        response = self.post(gallery_urls=json.dumps(urls))
        self.assertTrue(response.context["form"].has_error("gallery_files"))

    def test_fin_avant_debut_refusee(self):
        response = self.post(starts_at="2026-11-14T10:00", ends_at="2026-11-13T10:00")
        self.assertTrue(response.context["form"].has_error("ends_at"))

    def test_page_du_deal_galerie_code_promo_date_de_debut(self):
        import json

        from apps.deals.models import Deal

        self.post(
            gallery_urls=json.dumps(
                ["https://cdn.joybuy.nl/a.jpg", "https://cdn.joybuy.nl/b.jpg"]
            ),
            promo_code="SWITCH10",
            starts_at="2030-11-14T10:00",
        )
        deal = Deal.objects.get(external_url="https://www.joybuy.nl/switch-2")
        self.assertEqual(deal.image_url, "https://cdn.joybuy.nl/a.jpg")  # principale
        self.client.force_login(self.member)  # l'auteur voit son deal en attente
        html = self.client.get(deal.get_absolute_url()).content.decode()
        self.assertIn('data-photo="https://cdn.joybuy.nl/b.jpg"', html)
        self.assertIn("SWITCH10", html)
        self.assertIn('class="startsbanner"', html)
