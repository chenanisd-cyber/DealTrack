"""
Paiement par page hébergée (mode démonstration) : parcours complet,
tentatives de fraude, idempotence et webhook.
"""

from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.payments.models import Payment, Plan, Subscription

from .factories import make_user, seed_reference_data


class CheckoutFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.member = make_user("membre@example.be", "Membre")
        cls.other = make_user("autre@example.be", "Autre")
        cls.plan = Plan.objects.create(
            code="vip-test",
            name_fr="VIP test",
            name_nl="VIP test",
            name_de="VIP Test",
            price=Decimal("4.99"),
            vat_rate=Decimal("21.00"),
            duration_days=30,
        )

    def setUp(self):
        cache.clear()
        self.client.force_login(self.member)

    def start(self):
        response = self.client.post(
            reverse("payments:subscribe", args=[self.plan.code]), {"immediate_start": "on"}
        )
        self.assertEqual(response.status_code, 302)
        payment = Payment.objects.get(user=self.member, status=Payment.Status.PENDING)
        return response, payment

    def test_case_retractation_obligatoire(self):
        response = self.client.post(reverse("payments:subscribe", args=[self.plan.code]), {})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Payment.objects.exists())

    def test_redirection_vers_la_page_de_paiement(self):
        response, payment = self.start()
        self.assertTrue(payment.gateway_reference.startswith("cs_test_"))
        self.assertIn(payment.gateway_reference, response["Location"])

    def test_paiement_bancontact_cree_l_abonnement(self):
        _, payment = self.start()
        session = payment.gateway_reference
        page = reverse("payments:sandbox_checkout", args=[session])
        self.client.post(page, {"action": "bancontact"})  # le « prestataire » valide
        response = self.client.get(reverse("payments:checkout_return"), {"session_id": session})
        self.assertRedirects(response, reverse("accounts:profile"))
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(payment.card_brand, "bancontact")
        self.assertTrue(Subscription.objects.filter(payment=payment).exists())

    def test_retour_sans_paiement_ne_donne_rien(self):
        """Revenir sur l'URL de retour sans avoir payé ne crée pas d'abonnement."""
        _, payment = self.start()
        self.client.get(
            reverse("payments:checkout_return"), {"session_id": payment.gateway_reference}
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertFalse(Subscription.objects.exists())

    def test_refus_de_la_banque(self):
        _, payment = self.start()
        session = payment.gateway_reference
        self.client.post(
            reverse("payments:sandbox_checkout", args=[session]), {"action": "decline"}
        )
        self.client.get(reverse("payments:checkout_return"), {"session_id": session})
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertFalse(Subscription.objects.exists())

    def test_un_autre_membre_ne_peut_pas_utiliser_la_session(self):
        _, payment = self.start()
        self.client.force_login(self.other)
        response = self.client.get(
            reverse("payments:checkout_return"), {"session_id": payment.gateway_reference}
        )
        self.assertEqual(response.status_code, 404)

    def test_double_retour_un_seul_abonnement(self):
        _, payment = self.start()
        session = payment.gateway_reference
        self.client.post(
            reverse("payments:sandbox_checkout", args=[session]), {"action": "card"}
        )
        for _ in range(2):
            self.client.get(reverse("payments:checkout_return"), {"session_id": session})
        self.assertEqual(Subscription.objects.filter(user=self.member).count(), 1)

    def test_webhook_sans_signature_refuse(self):
        response = self.client.post(
            reverse("payments:stripe_webhook"),
            data='{"type": "checkout.session.completed"}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
