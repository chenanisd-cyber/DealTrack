"""
Espace commerçant, notifications par e-mail et application installable (PWA).
"""

import json
from datetime import timedelta
from io import StringIO

from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone, translation

from apps.accounts import notifications
from apps.accounts.models import Role
from apps.catalog.models import MerchantAccount
from apps.deals.models import Alert, AlertMatch, Comment, DealStatus
from apps.moderation.models import AuditLog

from .factories import make_deal, make_merchant, make_user, seed_reference_data

CLAIM = "Je suis le gérant du magasin, TVA BE0673617277."


class FrenchPagesMixin:
    def setUp(self):
        super().setUp()
        translation.activate("fr")
        self.addCleanup(translation.deactivate)


# --------------------------------------------------------------------------
# Espace commerçant
# --------------------------------------------------------------------------
class MerchantSpaceTests(FrenchPagesMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.owner = make_user("gerant@example.be", "Gerant")
        cls.other = make_user("autre@example.be", "Autre")
        cls.moderator = make_user("modo@example.be", "Modo", role=Role.MODERATOR)
        cls.shop = make_merchant("Librairie Dupont", city="Namur")
        cls.url = reverse("merchant:space")

    def claim(self, actor=None, merchant=None, **extra):
        self.client.force_login(actor or self.owner)
        data = {"merchant": str((merchant or self.shop).pk), "message": CLAIM, **extra}
        return self.client.post(self.url, data)

    def approve(self, user=None):
        account = MerchantAccount.objects.create(
            user=user or self.owner, merchant=self.shop, message=CLAIM
        )
        return account.decide(moderator=self.moderator, approve=True)

    def test_visiteur_renvoye_a_la_connexion(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_demande_enregistree_en_attente(self):
        response = self.claim()
        self.assertRedirects(response, self.url)
        account = MerchantAccount.objects.get(user=self.owner, merchant=self.shop)
        self.assertEqual(account.status, MerchantAccount.Status.PENDING)
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.MERCHANT_CLAIMED).exists()
        )

    def test_le_membre_ne_peut_pas_s_accepter_lui_meme(self):
        """Un champ « status » ajouté à la requête est ignoré : le serveur l'impose."""
        self.claim(status="approved", user=str(self.other.pk))
        account = MerchantAccount.objects.get(merchant=self.shop)
        self.assertEqual(account.status, MerchantAccount.Status.PENDING)
        self.assertEqual(account.user, self.owner)
        self.assertNotContains(self.client.get(self.url), "Publier une offre")

    def test_demande_en_double_refusee(self):
        self.claim()
        response = self.claim()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "déjà fait une demande")
        self.assertEqual(MerchantAccount.objects.count(), 1)

    def test_trois_demandes_en_attente_au_plus(self):
        for n in range(3):
            self.claim(merchant=make_merchant(f"Commerce {n}"))
        response = self.claim(merchant=make_merchant("Commerce de trop"))
        self.assertContains(response, "trois demandes en attente")
        self.assertEqual(MerchantAccount.objects.filter(user=self.owner).count(), 3)

    def test_justification_trop_courte_refusee(self):
        self.client.force_login(self.owner)
        self.client.post(self.url, {"merchant": str(self.shop.pk), "message": "moi"})
        self.assertFalse(MerchantAccount.objects.exists())

    def test_decision_datee_et_tracee(self):
        account = self.approve()
        self.assertEqual(account.status, MerchantAccount.Status.APPROVED)
        self.assertIsNotNone(account.decided_at)
        self.assertEqual(account.decided_by, self.moderator)
        entry = AuditLog.objects.get(action=AuditLog.Action.MERCHANT_CLAIM_DECIDED)
        self.assertTrue(entry.metadata["approved"])

    def test_tableau_de_bord_du_commercant(self):
        self.approve()
        live = make_deal(
            self.owner,
            merchant=self.shop,
            status=DealStatus.PUBLISHED,
            published_at=timezone.now(),
            title="Roman de la rentrée à 15 € au lieu de 22 €",
        )
        make_deal(
            self.owner, merchant=self.shop, title="Bande dessinée en attente de validation"
        )
        Comment.objects.create(deal=live, author=self.other, body="Très bonne librairie.")
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        board = response.context["dashboards"][0]
        self.assertEqual(board["merchant"], self.shop)
        self.assertEqual(board["stats"]["live"], 1)
        self.assertEqual(board["stats"]["pending"], 1)
        self.assertEqual(board["stats"]["comments"], 1)
        self.assertContains(response, "Roman de la rentrée")
        self.assertContains(response, f"?marchand={self.shop.pk}")  # « Publier une offre »

    def test_fiche_modifiable_par_son_commercant(self):
        self.approve()
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("merchant:edit", args=[self.shop.pk]),
            {
                "website": "https://librairie-dupont.example.be",
                "address": "Rue de Fer 12",
                "city": "Namur",
                "brand_color": "#0090E3",
                # Champs réservés à la modération : ignorés.
                "name": "Nom piraté",
                "is_verified": "on",
            },
        )
        self.assertRedirects(response, self.url)
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.website, "https://librairie-dupont.example.be")
        self.assertEqual(self.shop.address, "Rue de Fer 12")
        self.assertEqual(self.shop.name, "Librairie Dupont")
        self.assertFalse(self.shop.is_verified)
        self.assertTrue(
            AuditLog.objects.filter(action=AuditLog.Action.MERCHANT_UPDATED).exists()
        )

    def test_site_en_http_refuse(self):
        self.approve()
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("merchant:edit", args=[self.shop.pk]),
            {"website": "http://librairie.example.be", "brand_color": "#0090E3"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "https://")
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.website, "")

    def test_fiche_d_un_autre_commerce_introuvable(self):
        """404 et non 403 : on ne confirme pas l'existence de la fiche."""
        self.approve()
        url = reverse("merchant:edit", args=[self.shop.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"city": "Piraté"}).status_code, 404)

    def test_demande_en_attente_ou_refusee_n_ouvre_aucun_droit(self):
        account = MerchantAccount.objects.create(
            user=self.owner, merchant=self.shop, message=CLAIM
        )
        url = reverse("merchant:edit", args=[self.shop.pk])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 404)
        account.decide(moderator=self.moderator, approve=False)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_commerce_preselectionne_depuis_l_annuaire(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url, {"commerce": self.shop.slug})
        self.assertEqual(response.context["form"].initial["merchant"], self.shop)


# --------------------------------------------------------------------------
# Notifications par e-mail
# --------------------------------------------------------------------------
class EmailNotificationTests(FrenchPagesMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.author = make_user("auteur@example.be", "Auteur")
        cls.reader = make_user("lecteur@example.be", "Lecteur")
        cls.moderator = make_user("modo@example.be", "Modo", role=Role.MODERATOR)

    def setUp(self):
        super().setUp()
        self.deal = make_deal(self.author)
        mail.outbox.clear()

    def test_deal_publie_previent_son_auteur(self):
        self.deal.publish(moderator=self.moderator)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["auteur@example.be"])
        self.assertIn("en ligne", message.subject)
        self.assertIn(self.deal.title, message.body)
        self.assertIn(self.deal.get_absolute_url(), message.body)
        self.assertIn("/comptes/profil/modifier/", message.body)  # lien pour se désabonner

    def test_deal_refuse_reprend_le_motif(self):
        self.deal.reject(moderator=self.moderator, reason="Prix de référence non vérifiable")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Prix de référence non vérifiable", mail.outbox[0].body)

    def test_preference_coupee_aucun_envoi(self):
        self.author.notify_moderation = False
        self.author.save(update_fields=["notify_moderation"])
        self.deal.refresh_from_db()
        self.deal.publish(moderator=self.moderator)
        self.assertEqual(mail.outbox, [])

    def test_message_dans_la_langue_du_membre(self):
        self.author.preferred_language = "nl"
        self.author.save(update_fields=["preferred_language"])
        self.deal.refresh_from_db()
        self.deal.publish(moderator=self.moderator)
        self.assertIn("staat online", mail.outbox[0].subject)
        self.assertIn("/nl/comptes/profil/modifier/", mail.outbox[0].body)

    def test_compte_ferme_ne_recoit_plus_rien(self):
        self.author.soft_delete(actor=self.author)
        self.deal.refresh_from_db()
        self.assertFalse(notifications.deal_published(self.deal))
        self.assertEqual(mail.outbox, [])

    def comment(self, user, body="Merci pour ce bon plan, je le prends."):
        self.deal.status = DealStatus.PUBLISHED
        self.deal.published_at = timezone.now()
        self.deal.save()
        self.client.force_login(user)
        with self.captureOnCommitCallbacks(execute=True):
            url = reverse("deals:comment", args=[self.deal.slug])
            return self.client.post(url, {"body": body})

    def test_commentaire_previent_l_auteur_du_deal(self):
        self.comment(self.reader)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["auteur@example.be"])
        self.assertIn("Lecteur", message.body)
        self.assertIn("Merci pour ce bon plan", message.body)

    def test_son_propre_commentaire_ne_previent_personne(self):
        self.comment(self.author)
        self.assertEqual(mail.outbox, [])

    def test_preference_commentaires_coupee(self):
        self.author.notify_comments = False
        self.author.save(update_fields=["notify_comments"])
        self.comment(self.reader)
        self.assertEqual(mail.outbox, [])

    def test_panne_d_envoi_n_annule_pas_la_publication(self):
        with self.settings(EMAIL_BACKEND="tests.test_merchant_notifications_pwa.BrokenBackend"):
            self.deal.publish(moderator=self.moderator)
        self.deal.refresh_from_db()
        self.assertEqual(self.deal.status, DealStatus.PUBLISHED)

    def test_alertes_respectent_la_preference(self):
        alert = Alert.objects.create(user=self.reader, keyword="casque")
        self.deal.status = DealStatus.PUBLISHED
        self.deal.published_at = timezone.now()
        self.deal.save()
        # La publication a pu créer la correspondance : on la rend échue.
        match, _created = AlertMatch.objects.update_or_create(
            alert=alert,
            deal=self.deal,
            defaults={"available_at": timezone.now() - timedelta(minutes=1)},
        )
        self.reader.notify_alerts = False
        self.reader.save(update_fields=["notify_alerts"])
        call_command("send_alerts", stdout=StringIO())
        self.assertEqual(mail.outbox, [])
        match.refresh_from_db()
        self.assertIsNotNone(match.notified_at)  # traitée : pas de renvoi plus tard

    def test_preferences_modifiables_dans_le_profil(self):
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("accounts:profile-edit"),
            {"display_name": "Auteur", "preferred_language": "fr", "notify_alerts": "on"},
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        self.author.refresh_from_db()
        self.assertTrue(self.author.notify_alerts)
        self.assertFalse(self.author.notify_moderation)
        self.assertFalse(self.author.notify_comments)


class BrokenBackend:
    """Serveur d'envoi en panne, pour vérifier que l'action continue."""

    def __init__(self, *args, **kwargs):
        pass

    def send_messages(self, messages):
        raise OSError("serveur SMTP injoignable")


# --------------------------------------------------------------------------
# Application installable (PWA)
# --------------------------------------------------------------------------
class InstallableAppTests(FrenchPagesMixin, TestCase):
    def test_manifeste(self):
        response = self.client.get("/manifest.webmanifest")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/manifest+json"))
        data = json.loads(response.content)
        self.assertEqual(data["display"], "standalone")
        self.assertEqual(data["start_url"], "/fr/?source=pwa")
        self.assertEqual(data["scope"], "/")
        sizes = {icon["sizes"] for icon in data["icons"]}
        self.assertEqual(sizes, {"192x192", "512x512"})
        self.assertTrue(any(icon.get("purpose") == "maskable" for icon in data["icons"]))

    def test_icones_presentes(self):
        folder = settings.FRONTEND_DIR / "static" / "img"
        for name in ("icon-192.png", "icon-512.png", "icon-maskable-512.png", "icon-180.png"):
            self.assertTrue((folder / name).is_file(), name)

    def test_service_worker_a_la_racine(self):
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("application/javascript"))
        self.assertEqual(response["Service-Worker-Allowed"], "/")
        self.assertEqual(response["Cache-Control"], "no-cache")
        script = response.content.decode()
        self.assertIn('const OFFLINE_URL = "/hors-ligne/"', script)
        self.assertIn("/static/css/dealtrack.css", script)
        # Aucune page du site n'est gardée sur l'appareil.
        self.assertNotIn("/comptes/", script)

    def test_page_hors_ligne(self):
        response = self.client.get("/hors-ligne/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hors ligne")

    def test_pages_declarent_l_application(self):
        html = self.client.get(reverse("deals:list")).content.decode()
        self.assertIn('<link rel="manifest" href="/manifest.webmanifest">', html)
        self.assertIn("apple-touch-icon", html)
        self.assertIn("data-install", html)
        # Le bandeau d'installation reste masqué tant que le navigateur ne le propose pas.
        self.assertIn("data-install hidden", html)


# --------------------------------------------------------------------------
# Recherche de commerçants
# --------------------------------------------------------------------------
class MerchantSearchTests(FrenchPagesMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        local = {"is_local_independent": True, "country": "BE"}
        cls.bakery = make_merchant(
            "Boulangerie Dupont",
            city="Namur",
            shop_type="bakery",
            address="Rue de Fer 3",
            **local,
        )
        cls.books = make_merchant("Librairie Molière", city="Liège", shop_type="books", **local)
        cls.chain = make_merchant("Dupont Électro")  # enseigne non locale : hors annuaire
        cls.url = reverse("deals:local")

    def found(self, q, **extra):
        return set(self.client.get(self.url, {"q": q, **extra}).context["merchants"])

    def test_par_nom_sans_tenir_compte_de_la_casse(self):
        self.assertEqual(self.found("dupont"), {self.bakery})
        self.assertEqual(self.found("LIBRAIRIE"), {self.books})

    def test_par_ville_adresse_et_type_de_commerce(self):
        self.assertEqual(self.found("liège"), {self.books})
        self.assertEqual(self.found("rue de fer"), {self.bakery})
        self.assertEqual(self.found("librairie namur"), set())  # tous les mots sont exigés
        # Le type est stocké « bakery » : son libellé français est cherché aussi.
        self.bakery.name = "Chez Dupont"
        self.bakery.save(update_fields=["name"])
        self.assertEqual(self.found("boulangerie"), {self.bakery})

    def test_recherche_combinee_avec_la_ville(self):
        self.assertEqual(self.found("dupont", ville="Liège"), set())
        self.assertEqual(self.found("dupont", ville="Namur"), {self.bakery})

    def test_aucun_resultat(self):
        response = self.client.get(self.url, {"q": "poissonnerie"})
        self.assertContains(response, "Aucun commerçant ne correspond à « poissonnerie »")

    def test_texte_affiche_echappe(self):
        response = self.client.get(self.url, {"q": "<script>alert(1)</script>"})
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_sur_l_annuaire_la_barre_cherche_un_commercant(self):
        html = self.client.get(self.url).content.decode()
        self.assertIn(f'role="search" method="get" action="{self.url}"', html)
        home = self.client.get(reverse("deals:list")).content.decode()
        self.assertIn(f'role="search" method="get" action="{reverse("deals:list")}"', home)

    def test_recherche_de_deals_propose_aussi_les_commercants(self):
        """Un commerce sans aucun deal reste trouvable depuis la barre de l'accueil."""
        response = self.client.get(reverse("deals:list"), {"q": "dupont"})
        self.assertEqual(response.context["merchant_hits"], [self.bakery])
        self.assertContains(response, "Commerçants locaux correspondants")
        self.assertContains(response, "Boulangerie Dupont")
        self.assertNotContains(response, "Dupont Électro")
