"""
Abonnement VIP : historique du prix, comparaison, alertes en priorité.
"""

from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.deals.models import Alert, AlertMatch, Deal, DealStatus, PricePoint
from apps.deals.vip import ALERT_DELAY, product_name, similar_deals
from apps.payments.models import Payment, Plan, Subscription

from .factories import make_deal, make_merchant, make_user, seed_reference_data


def make_vip(user):
    plan = Plan.objects.get(code="vip-annuel")
    payment = Payment.objects.create(
        reference=Payment.next_reference(),
        user=user,
        plan=plan,
        amount=plan.price,
        vat_amount=Decimal("4.17"),
        status=Payment.Status.SUCCEEDED,
        gateway="sandbox",
        gateway_reference=f"sbx_test_{user.pk.hex[:10]}",
        settled_at=timezone.now(),
    )
    Subscription.objects.create(
        user=user, plan=plan, payment=payment, ends_at=timezone.now() + timedelta(days=30)
    )
    user.__dict__.pop("is_vip", None)  # vide le cache de la propriété
    return user


class VipTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.author = make_user("auteur@example.be", "Auteur")
        cls.member = make_user("membre@example.be", "Membre")
        cls.vip = make_vip(make_user("vip@example.be", "Vip"))
        cls.deal = make_deal(
            cls.author,
            title="TV Philips Ambilight 43 PUS8001 à 349 € au lieu de 449 €",
            status=DealStatus.PUBLISHED,
            published_at=timezone.now(),
            price=Decimal("349.00"),
            reference_price=Decimal("449.00"),
        )


class VipStatusTests(VipTestCase):
    def test_abonnement_actif(self):
        self.assertTrue(self.vip.is_vip)
        self.assertFalse(self.member.is_vip)

    def test_formules_renommees(self):
        self.assertTrue(Plan.objects.filter(code="vip-annuel", name_fr="VIP annuel").exists())


class PriceHistoryTests(VipTestCase):
    def test_point_a_la_creation_puis_a_chaque_changement(self):
        self.assertEqual(self.deal.price_history.count(), 1)
        self.deal.price = Decimal("329.00")
        self.deal.save()
        self.deal.save()  # même prix : pas de nouveau point
        self.assertEqual(
            list(self.deal.price_history.values_list("price", "source")),
            [(Decimal("349.00"), "survey"), (Decimal("329.00"), "update")],
        )

    def test_graphique_reserve_aux_vip(self):
        page = self.client.get(self.deal.get_absolute_url()).content.decode()
        self.assertIn("Réservé aux membres VIP", page)
        self.assertNotIn('class="pricechart__dot"', page)

        self.client.force_login(self.vip)
        page = self.client.get(self.deal.get_absolute_url()).content.decode()
        self.assertIn('class="pricechart__dot"', page)
        self.assertIn("449,00 €", page)  # ligne du prix de référence
        self.assertNotIn('cy="152,0"', page)  # coordonnées SVG sans virgule décimale

    def test_un_seul_releve_trace_une_ligne_plate(self):
        from apps.deals.vip import price_chart

        chart = price_chart(self.deal)
        self.assertEqual(chart["count"], 1)
        start, end = chart["polyline"].split()
        self.assertEqual(start.split(",")[1], end.split(",")[1])  # même hauteur
        self.assertNotEqual(start, end)

    def test_styles_recharges_apres_modification(self):
        page = self.client.get(self.deal.get_absolute_url()).content.decode()
        self.assertRegex(page, r"dealtrack\.css\?v=[0-9a-f]{10}")


class ComparisonTests(VipTestCase):
    def test_meme_produit_chez_un_autre_marchand(self):
        other = make_deal(
            self.author,
            title="TV Philips Ambilight 43 PUS8001 à 339 € au lieu de 449 €",
            merchant=make_merchant("Krëfel"),
            status=DealStatus.PUBLISHED,
            published_at=timezone.now(),
            price=Decimal("339.00"),
        )
        self.assertIn(other, similar_deals(self.deal))

    def test_nom_du_produit_sans_le_prix(self):
        self.assertEqual(product_name(self.deal.title), "TV Philips Ambilight 43 PUS8001")

    def test_comparaison_en_direct_reservee_aux_vip(self):
        url = reverse("deals:compare", args=[self.deal.slug])
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.vip)
        offers = [
            {
                "title": "Philips 43PUS8001",
                "price": "345.00",
                "url": "https://www.amazon.com.be/dp/X",
            }
        ]
        with mock.patch("apps.deals.vip.amazon_offers", return_value=offers):
            response = self.client.get(url)
        self.assertEqual(response.json(), {"amazon": offers})
        # Réponse propre à l'utilisateur : jamais gardée dans le cache du navigateur.
        self.assertIn("no-store", response["Cache-Control"])


class AlertPriorityTests(VipTestCase):
    def test_vip_tout_de_suite_les_autres_apres_le_delai(self):
        vip_alert = Alert.objects.create(user=self.vip, keyword="ambilight")
        member_alert = Alert.objects.create(user=self.member, keyword="ambilight")
        deal = make_deal(
            self.author,
            title="TV Philips Ambilight 50 PQS9001 à 699 € au lieu de 899 €",
            status=DealStatus.PENDING,
        )
        before = timezone.now()
        deal.status = DealStatus.PUBLISHED
        deal.published_at = timezone.now()
        deal.save()

        vip_match = AlertMatch.objects.get(alert=vip_alert, deal=deal)
        member_match = AlertMatch.objects.get(alert=member_alert, deal=deal)
        self.assertTrue(vip_match.is_priority)
        self.assertLess(vip_match.available_at, member_match.available_at)
        self.assertGreaterEqual(member_match.available_at, before + ALERT_DELAY)

    def test_prix_maximum_respecte(self):
        Alert.objects.create(user=self.vip, keyword="tv", max_price=Decimal("300"))
        deal = make_deal(
            self.author,
            title="TV Samsung LED 50 U8070H à 399 €",
            status="pending",
            price=Decimal("399.00"),
            reference_price=None,
        )
        deal.status, deal.published_at = DealStatus.PUBLISHED, timezone.now()
        deal.save()
        self.assertFalse(AlertMatch.objects.filter(deal=deal).exists())

    def test_envoi_des_seules_alertes_echues(self):
        alert = Alert.objects.create(user=self.member, keyword="ambilight")
        AlertMatch.objects.create(alert=alert, deal=self.deal, available_at=timezone.now())
        later = make_deal(self.author, status=DealStatus.PUBLISHED, published_at=timezone.now())
        AlertMatch.objects.create(
            alert=alert, deal=later, available_at=timezone.now() + timedelta(hours=2)
        )
        call_command("send_alerts", stdout=StringIO())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.deal.title, mail.outbox[0].body)
        self.assertNotIn(later.title, mail.outbox[0].body)

    def test_page_mes_alertes(self):
        self.client.force_login(self.member)
        response = self.client.post(reverse("accounts:alerts"), {"keyword": "airfryer"})
        self.assertRedirects(response, reverse("accounts:alerts"))
        alert = Alert.objects.get(user=self.member, keyword="airfryer")
        self.client.post(reverse("accounts:alert-delete", args=[alert.pk]))
        self.assertFalse(Alert.objects.filter(pk=alert.pk).exists())


class RegionsRemovedTests(VipTestCase):
    def test_plus_de_filtre_par_region(self):
        page = self.client.get(reverse("deals:list")).content.decode()
        self.assertNotIn("Toute la Belgique", page)
        self.assertFalse(hasattr(Deal, "regions"))
        self.assertFalse(PricePoint.objects.filter(price__lt=0).exists())
