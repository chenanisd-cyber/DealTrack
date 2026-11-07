"""
Pré-remplissage du dépôt par lien : protection SSRF, accès et formulaire.

Aucun test ne sort sur Internet : la résolution DNS (socket.getaddrinfo) et
le téléchargement (requests.get) sont simulés avec unittest.mock.
"""

import json
import socket
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.deals import scraper

from .factories import make_user, seed_reference_data


def fake_dns(ip):
    """Simule getaddrinfo : le nom de domaine se résout vers `ip`."""
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    return mock.patch.object(
        scraper.socket,
        "getaddrinfo",
        return_value=[(family, socket.SOCK_STREAM, 6, "", (ip, 443))],
    )


def fake_response(body=b"", status=200, location=None):
    response = mock.Mock()
    response.status_code = status
    response.is_redirect = location is not None
    response.headers = {"Location": location} if location else {}
    response.iter_content.return_value = [body]
    response.raise_for_status.return_value = None
    return response


PAGE = (
    b"<html><head><title>Casque Sony | Boutique</title>"
    b'<meta property="og:image" content="/img/casque.jpg">'
    b"</head><body></body></html>"
)


class ValidatePublicUrlTests(TestCase):
    def test_refuse_les_schemas_autres_que_http(self):
        for url in ("file:///etc/passwd", "ftp://example.com/", "javascript:alert(1)"):
            with self.assertRaises(scraper.UnsafeURLError, msg=url):
                scraper.validate_public_url(url)

    def test_refuse_les_adresses_non_publiques(self):
        for ip in ("127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "::1"):
            with fake_dns(ip), self.assertRaises(scraper.UnsafeURLError, msg=ip):
                scraper.validate_public_url("https://piege.example/")

    def test_accepte_une_adresse_publique(self):
        with fake_dns("93.184.216.34"):
            scraper.validate_public_url("https://www.example.com/")


class FetchDealInfoTests(TestCase):
    def test_extrait_titre_et_image_absolue(self):
        with (
            fake_dns("93.184.216.34"),
            mock.patch.object(scraper.requests, "get", return_value=fake_response(PAGE)),
        ):
            info = scraper.fetch_deal_info("https://shop.example/produit")

        self.assertTrue(info["success"])
        self.assertEqual(info["title"], "Casque Sony")
        self.assertEqual(info["image_url"], "https://shop.example/img/casque.jpg")

    def test_redirection_vers_localhost_refusee(self):
        """Une page publique ne doit pas pouvoir rediriger vers le serveur lui-même."""
        redirect = fake_response(status=302, location="http://127.0.0.1/admin")
        dns = mock.patch.object(
            scraper.socket,
            "getaddrinfo",
            side_effect=[
                [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))],
                [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))],
            ],
        )
        with dns, mock.patch.object(scraper.requests, "get", return_value=redirect) as get:
            info = scraper.fetch_deal_info("https://shop.example/")

        self.assertEqual(info, {"success": False, "error": "unsafe_url"})
        self.assertEqual(get.call_count, 1)  # la cible interne n'a jamais été appelée

    def test_erreur_reseau_message_generique(self):
        with (
            fake_dns("93.184.216.34"),
            mock.patch.object(
                scraper.requests,
                "get",
                side_effect=scraper.requests.ConnectionError("détail interne"),
            ),
        ):
            info = scraper.fetch_deal_info("https://shop.example/")

        self.assertEqual(info, {"success": False, "error": "unreachable"})


class ScrapeViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.member = make_user("membre@example.be", "Membre")

    def setUp(self):
        cache.clear()
        self.url = reverse("deals:scrape-link")

    def post(self, payload):
        return self.client.post(self.url, json.dumps(payload), content_type="application/json")

    def test_anonyme_redirige_vers_la_connexion(self):
        response = self.post({"url": "https://shop.example/"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_corps_invalide(self):
        self.client.force_login(self.member)
        response = self.client.post(self.url, "pas du json", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_limite_d_appels(self):
        self.client.force_login(self.member)
        with mock.patch(
            "apps.deals.views.fetch_deal_info", return_value={"success": False, "error": "x"}
        ):
            codes = [self.post({"url": "https://shop.example/"}).status_code for _ in range(11)]
        self.assertEqual(codes[:10], [200] * 10)
        self.assertEqual(codes[10], 429)


class SubmitFormDisplayTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.member = make_user("membre@example.be", "Membre")

    def test_erreurs_visibles_apres_envoi_invalide(self):
        """Après un envoi invalide, l'étape 2 (et ses erreurs) doit être affichée."""
        self.client.force_login(self.member)
        response = self.client.post(reverse("deals:submit"), {"title": "trop court"})
        html = response.content.decode()

        self.assertEqual(response.status_code, 200)
        self.assertIn('<div id="step1-link" hidden>', html)
        self.assertIn('<div id="step2-form">', html)

    def test_premier_affichage_commence_par_le_lien(self):
        self.client.force_login(self.member)
        html = self.client.get(reverse("deals:submit")).content.decode()
        self.assertIn('<div id="step1-link">', html)
        self.assertIn('<div id="step2-form" hidden>', html)
