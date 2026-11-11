"""
Favoris, signalement d'un deal et modification du profil.

Chaque interdiction est testée avec l'autorisation qui lui répond : un membre
peut signaler le deal d'un autre, mais pas le sien ; il peut changer son
pseudonyme, mais pas son e-mail ni son rôle.
"""

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import translation

from apps.accounts.models import Role, User
from apps.deals.models import DealStatus, Favorite
from apps.moderation.models import AuditLog, Report

from .factories import make_deal, make_user, seed_reference_data


class MemberFeatureTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.author = make_user("auteur@example.be", "Auteur")
        cls.member = make_user("membre@example.be", "Membre")
        cls.deal = make_deal(cls.author, status=DealStatus.PUBLISHED)
        cls.pending = make_deal(cls.author, status=DealStatus.PENDING)

    def setUp(self):
        translation.activate("fr")
        self.addCleanup(translation.deactivate)


class FavoriteTests(MemberFeatureTestCase):
    def url(self, deal=None):
        return reverse("deals:favorite", args=[(deal or self.deal).slug])

    def test_ajouter_puis_retirer(self):
        self.client.force_login(self.member)
        self.client.post(self.url())
        self.assertTrue(Favorite.objects.filter(user=self.member, deal=self.deal).exists())
        self.client.post(self.url())
        self.assertFalse(Favorite.objects.filter(user=self.member, deal=self.deal).exists())

    def test_visiteur_redirige_vers_la_connexion(self):
        response = self.client.post(self.url())
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])
        self.assertFalse(Favorite.objects.exists())

    def test_get_refuse(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url()).status_code, 405)

    def test_deal_non_visible_introuvable(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.post(self.url(self.pending)).status_code, 404)

    def test_un_seul_favori_par_membre_et_par_deal(self):
        Favorite.objects.create(user=self.member, deal=self.deal)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Favorite.objects.create(user=self.member, deal=self.deal)

    def test_page_mes_favoris(self):
        Favorite.objects.create(user=self.member, deal=self.deal)
        self.client.force_login(self.member)
        response = self.client.get(reverse("accounts:favorites"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["deals"]), [self.deal])

    def test_page_mes_favoris_ne_montre_pas_ceux_des_autres(self):
        Favorite.objects.create(user=self.author, deal=self.deal)
        self.client.force_login(self.member)
        response = self.client.get(reverse("accounts:favorites"))
        self.assertEqual(list(response.context["deals"]), [])

    def test_favoris_dans_l_export_rgpd(self):
        Favorite.objects.create(user=self.member, deal=self.deal)
        data = self.member.export_personal_data()
        self.assertEqual(len(data["favoris"]), 1)


class ReportTests(MemberFeatureTestCase):
    def url(self, deal=None):
        return reverse("deals:report", args=[(deal or self.deal).slug])

    def test_signalement_enregistre_et_trace(self):
        self.client.force_login(self.member)
        self.client.post(self.url(), {"reason": "wrong_price", "detail": "Le prix a changé."})
        report = Report.objects.get()
        self.assertEqual(
            (report.reporter, report.reason, report.status),
            (self.member, "wrong_price", "open"),
        )
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.DEAL_REPORTED).exists())

    def test_un_seul_signalement_par_membre(self):
        self.client.force_login(self.member)
        self.client.post(self.url(), {"reason": "spam"})
        response = self.client.post(self.url(), {"reason": "misleading"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Report.objects.count(), 1)

    def test_auteur_ne_peut_pas_signaler_son_deal(self):
        self.client.force_login(self.author)
        self.client.post(self.url(), {"reason": "spam"})
        self.assertFalse(Report.objects.exists())

    def test_motif_invalide_refuse(self):
        self.client.force_login(self.member)
        self.client.post(self.url(), {"reason": "pas-un-motif"})
        self.assertFalse(Report.objects.exists())

    def test_visiteur_ne_peut_pas_signaler(self):
        self.client.post(self.url(), {"reason": "spam"})
        self.assertFalse(Report.objects.exists())

    def test_formulaire_visible_sur_la_page_du_deal(self):
        self.client.force_login(self.member)
        page = self.client.get(self.deal.get_absolute_url()).content.decode()
        self.assertIn(self.url(), page)

    def test_formulaire_absent_pour_l_auteur(self):
        self.client.force_login(self.author)
        page = self.client.get(self.deal.get_absolute_url()).content.decode()
        self.assertNotIn(self.url(), page)

    def test_moderateur_voit_les_signalements_dans_le_back_office(self):
        from io import StringIO

        from django.core.management import call_command

        # setup_roles place les modérateurs existants dans leur groupe.
        moderator = make_user("mod@example.be", "Moderateur", role=Role.MODERATOR)
        call_command("setup_roles", stdout=StringIO())
        Report.objects.create(deal=self.deal, reporter=self.member, reason="spam")
        self.client.force_login(moderator)
        response = self.client.get(reverse("admin:moderation_report_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Spam")


class ProfileEditTests(MemberFeatureTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("accounts:profile-edit")

    def test_modifier_pseudonyme_langue_et_consentement(self):
        self.client.force_login(self.member)
        response = self.client.post(
            self.url,
            {
                "display_name": "NouveauNom",
                "preferred_language": "nl",
                "marketing_consent": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.member.refresh_from_db()
        self.assertEqual(
            (
                self.member.display_name,
                self.member.preferred_language,
                self.member.marketing_consent,
            ),
            ("NouveauNom", "nl", True),
        )
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.USER_UPDATED).exists())

    def test_pseudonyme_deja_pris_refuse(self):
        self.client.force_login(self.member)
        response = self.client.post(
            self.url, {"display_name": "auteur", "preferred_language": "fr"}
        )
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertEqual(self.member.display_name, "Membre")

    def test_garder_son_propre_pseudonyme_accepte(self):
        self.client.force_login(self.member)
        response = self.client.post(
            self.url, {"display_name": "Membre", "preferred_language": "de"}
        )
        self.assertEqual(response.status_code, 302)

    def test_email_et_role_non_modifiables(self):
        self.client.force_login(self.member)
        self.client.post(
            self.url,
            {
                "display_name": "Membre",
                "preferred_language": "fr",
                "email": "pirate@example.be",
                "role": Role.ADMIN,
                "is_staff": "on",
            },
        )
        member = User.objects.get(pk=self.member.pk)
        self.assertEqual(
            (member.email, member.role, member.is_staff),
            ("membre@example.be", Role.MEMBER, False),
        )

    def test_visiteur_redirige(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
