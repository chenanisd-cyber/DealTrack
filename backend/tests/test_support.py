"""
Barre de recherche et page « Aide et contact ».
"""

from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone, translation

from apps.deals.models import DealStatus, DealTranslation
from apps.moderation.models import ContactMessage

from .factories import make_deal, make_merchant, make_user, seed_reference_data


class SearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        author = make_user("auteur@example.be", "Auteur")
        published = {"status": DealStatus.PUBLISHED, "published_at": timezone.now()}
        cls.dyson = make_deal(
            author, title="Aspirateur Dyson V12 Detect Slim à 419 €", **published
        )
        cls.tv = make_deal(author, title="TV Philips Ambilight 43 pouces à 349 €", **published)
        cls.local = make_deal(
            author,
            title="Pain au levain bio à 3 €",
            merchant=make_merchant("Boulangerie Dupont"),
            **published,
        )
        DealTranslation.objects.create(
            deal=cls.tv, language="nl", title="Philips Ambilight televisie", description="Tv"
        )
        cls.hidden = make_deal(author, title="Aspirateur caché en attente", status="pending")

    def setUp(self):
        translation.activate("fr")
        self.addCleanup(translation.deactivate)

    def search(self, q, **extra):
        return self.client.get(reverse("deals:list"), {"q": q, **extra}).content.decode()

    def results(self, q):
        """Deals de la liste de résultats (la colonne « Les plus hot » n'en fait pas partie)."""
        response = self.client.get(reverse("deals:list"), {"q": q})
        return set(response.context["page_obj"].object_list)

    def test_un_mot_trouve_le_bon_deal(self):
        self.assertEqual(self.results("dyson"), {self.dyson})  # majuscules indifférentes
        self.assertIn("Résultats pour « dyson »", self.search("dyson"))

    def test_tous_les_mots_doivent_correspondre(self):
        self.assertEqual(self.results("aspirateur slim"), {self.dyson})

    def test_marchand_et_traduction(self):
        self.assertEqual(self.results("boulangerie"), {self.local})
        self.assertEqual(self.results("televisie"), {self.tv})  # titre néerlandais

    def test_deal_non_publie_jamais_trouve(self):
        self.assertNotIn(self.hidden, self.results("aspirateur"))

    def test_aucun_resultat_et_texte_malveillant(self):
        page = self.search("zzzintrouvable")
        self.assertIn("Aucun deal ne correspond à « zzzintrouvable »", page)
        response = self.client.get(reverse("deals:list"), {"q": "' OR 1=1--<script>"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("<script>", response.content.decode())

    def test_onglets_gardent_la_recherche(self):
        self.assertIn("?q=dyson&amp;tri=new", self.search("dyson"))


class ContactTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.member = make_user("membre@example.be", "Membre")

    def setUp(self):
        cache.clear()
        translation.activate("fr")
        self.addCleanup(translation.deactivate)
        self.url = reverse("support:contact")

    def valid(self, **extra):
        data = {
            "name": "Claire Dubois",
            "email": "claire@example.be",
            "subject": "question",
            "message": "Bonjour, comment est calculée la température d'un deal ?",
            "website": "",
        }
        data.update(extra)
        return data

    def test_page_avec_faq_et_lien_dans_le_pied_de_page(self):
        page = self.client.get(self.url).content.decode()
        self.assertIn("Questions fréquentes", page)
        self.assertIn("Comment publier un bon plan ?", page)
        home = self.client.get(reverse("deals:list")).content.decode()
        self.assertIn(self.url, home)

    def test_message_enregistre_et_equipe_prevenue(self):
        response = self.client.post(self.url, self.valid())
        self.assertRedirects(response, self.url)
        message = ContactMessage.objects.get()
        self.assertEqual((message.status, message.language), ("new", "fr"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("support@dealtrack.be", mail.outbox[0].to)

    def test_membre_connecte_prerempli_et_rattache(self):
        self.client.force_login(self.member)
        page = self.client.get(self.url).content.decode()
        self.assertIn('value="membre@example.be"', page)
        self.client.post(self.url, self.valid(email="membre@example.be"))
        self.assertEqual(ContactMessage.objects.get().user, self.member)

    def test_message_trop_court_ou_robot_refuse(self):
        self.client.post(self.url, self.valid(message="Trop court"))
        self.client.post(self.url, self.valid(website="http://spam.example"))
        self.client.post(self.url, self.valid(email="pas-un-email"))
        self.assertFalse(ContactMessage.objects.exists())

    def test_limite_de_cinq_messages_par_heure(self):
        for _ in range(5):
            self.client.post(self.url, self.valid())
        response = self.client.post(self.url, self.valid())
        self.assertEqual(response.status_code, 429)
        self.assertEqual(ContactMessage.objects.count(), 5)

    def test_csrf_obligatoire(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.url, self.valid()).status_code, 403)
        self.assertFalse(ContactMessage.objects.exists())
