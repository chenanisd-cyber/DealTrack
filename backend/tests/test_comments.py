"""
Commentaires multilingues : traduction affichée selon la langue de la page,
repli sur l'original signalé, langue de rédaction enregistrée à l'envoi.
"""

from django.test import TestCase
from django.utils import timezone

from apps.deals.models import Comment, CommentTranslation, DealStatus

from .factories import make_deal, make_user, seed_reference_data

ORIGINAL = "Livraison en deux jours ouvrables jusqu'à Liège, emballage soigné."
DUTCH = "Levering in twee werkdagen tot in Luik, zorgvuldig verpakt."


class CommentTranslationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.member = make_user("membre@example.be", "Membre")
        cls.deal = make_deal(
            cls.member, status=DealStatus.PUBLISHED, published_at=timezone.now()
        )
        cls.comment = Comment.objects.create(
            deal=cls.deal, author=cls.member, body=ORIGINAL, language="fr"
        )
        CommentTranslation.objects.create(comment=cls.comment, language="nl", body=DUTCH)

    def page(self, language):
        return self.client.get(f"/{language}/deal/{self.deal.slug}/").content.decode()

    def test_page_francaise_affiche_l_original_sans_mention(self):
        html = self.page("fr")
        self.assertIn("Livraison en deux jours", html)
        self.assertNotIn('class="comment__lang"', html)

    def test_page_neerlandaise_affiche_la_traduction(self):
        html = self.page("nl")
        self.assertIn(DUTCH, html)
        self.assertNotIn("Livraison en deux jours", html)
        self.assertIn('class="comment__lang"', html)  # « Vertaald — origineel in het … »

    def test_sans_traduction_l_original_est_signale(self):
        html = self.page("de")  # aucune traduction allemande
        self.assertIn("Livraison en deux jours", html)
        self.assertIn('class="comment__lang"', html)

    def test_langue_de_redaction_enregistree_a_l_envoi(self):
        self.client.force_login(self.member)
        self.client.post(
            f"/nl/deal/{self.deal.slug}/commentaire/", {"body": "Goede prijs, bedankt!"}
        )
        comment = Comment.objects.get(body="Goede prijs, bedankt!")
        self.assertEqual(comment.language, "nl")

    def test_une_seule_traduction_par_langue(self):
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            CommentTranslation.objects.create(comment=self.comment, language="nl", body="x")
