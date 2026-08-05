"""
Tests unitaires — une couche à la fois, sans HTTP.

On teste surtout ce qui garde la base cohérente : les contraintes, la logique
de vote concurrent, la suppression logique et la politique de mot de passe.
"""

from decimal import Decimal

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.accounts.validators import ComplexityValidator, validate_be_vat
from apps.catalog.models import Category, CategoryTranslation, Merchant
from apps.deals.models import Deal, DealStatus, Vote
from apps.payments.gateways import PaymentError, SandboxGateway
from apps.payments.models import Payment, Plan
from apps.payments.services import purchase_subscription

from .factories import make_deal, make_user, seed_reference_data


class PasswordPolicyTests(TestCase):
    """La politique doit refuser ce qu'un attaquant essaie en premier."""

    def test_rejects_too_short(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_password("Ab3!xY9z")  # 8 caractères
        self.assertTrue(any("12" in m for m in ctx.exception.messages))

    def test_rejects_common_password(self):
        with self.assertRaises(ValidationError):
            validate_password("motdepasse123")

    def test_rejects_keyboard_sequence(self):
        with self.assertRaises(ValidationError) as ctx:
            ComplexityValidator().validate("Azertyuiop-42!")
        self.assertEqual(ctx.exception.code, "password_sequential")

    def test_rejects_single_character_class(self):
        with self.assertRaises(ValidationError) as ctx:
            ComplexityValidator().validate("aaaabbbbccccdddd")
        self.assertEqual(ctx.exception.code, "password_not_complex")

    def test_rejects_password_similar_to_email(self):
        # UserAttributeSimilarityValidator découpe l'adresse en segments sur les
        # non-alphanumériques : le mot de passe doit ressembler à un segment,
        # pas seulement à l'adresse complète.
        user = User(email="charlottemertens@example.be", display_name="ChaMe")
        with self.assertRaises(ValidationError) as ctx:
            validate_password("CharlotteMertens1!", user=user)
        # On assert sur le code, pas sur le texte : celui-ci est traduit.
        self.assertIn("password_too_similar", [e.code for e in ctx.exception.error_list])

    def test_accepts_strong_password(self):
        validate_password("Tram-81-Vers-Ixelles")  # ne doit rien lever


class VatValidatorTests(TestCase):
    def test_accepts_real_belgian_numbers(self):
        for number in ("BE0403170701", "BE0400378485", "BE0202239951"):
            validate_be_vat(number)

    def test_accepts_formatted_input(self):
        validate_be_vat("BE 0403.170.701")

    def test_rejects_bad_checksum(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_be_vat("BE0403170702")
        self.assertEqual(ctx.exception.code, "vat_checksum")

    def test_rejects_foreign_format(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_be_vat("FR12345678901")
        self.assertEqual(ctx.exception.code, "vat_format")


class DatabaseConstraintTests(TestCase):
    """Les garde-fous doivent tenir au niveau SQL, pas seulement en Python."""

    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.user = make_user("contrainte@example.be", "Contrainte")

    def test_reference_price_must_exceed_price(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_deal(self.user, price=Decimal("100.00"), reference_price=Decimal("80.00"))

    def test_negative_price_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_deal(self.user, price=Decimal("-5.00"))

    def test_end_date_must_follow_start(self):
        now = timezone.now()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_deal(self.user, starts_at=now, ends_at=now - timezone.timedelta(hours=1))

    def test_published_deal_requires_publication_date(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                make_deal(self.user, status=DealStatus.PUBLISHED, published_at=None)

    def test_one_vote_per_user_and_deal(self):
        deal = make_deal(self.user, status=DealStatus.PUBLISHED, published_at=timezone.now())
        voter = make_user("votant@example.be", "Votant")
        Vote.objects.create(deal=deal, user=voter, value=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Vote.objects.create(deal=deal, user=voter, value=-1)

    def test_vote_value_limited_to_plus_or_minus_one(self):
        deal = make_deal(self.user, status=DealStatus.PUBLISHED, published_at=timezone.now())
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Vote.objects.create(deal=deal, user=self.user, value=5)

    def test_category_translation_unique_per_language(self):
        category = Category.objects.get(slug="high-tech")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CategoryTranslation.objects.create(
                    category=category, language="fr", name="Doublon"
                )

    def test_local_merchant_must_be_belgian(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Merchant.objects.create(
                    name="Faux local",
                    slug="faux-local",
                    country="NL",
                    is_local_independent=True,
                )

    def test_vat_amount_cannot_exceed_total(self):
        plan = Plan.objects.first()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Payment.objects.create(
                    reference="DT-9999-000001",
                    user=self.user,
                    plan=plan,
                    amount=Decimal("10.00"),
                    vat_amount=Decimal("15.00"),
                    gateway_reference="x-1",
                )


class VoteLogicTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.author = make_user("auteur@example.be", "Auteur")
        cls.deal = make_deal(
            cls.author, status=DealStatus.PUBLISHED, published_at=timezone.now()
        )

    def test_first_vote_moves_temperature(self):
        voter = make_user("v1@example.be", "V1")
        self.assertEqual(Vote.cast(deal=self.deal, user=voter, value=1), 101)

    def test_revoting_same_direction_cancels(self):
        voter = make_user("v2@example.be", "V2")
        Vote.cast(deal=self.deal, user=voter, value=1)
        self.assertEqual(Vote.cast(deal=self.deal, user=voter, value=1), 100)
        self.assertFalse(Vote.objects.filter(deal=self.deal, user=voter).exists())

    def test_switching_direction_applies_double_delta(self):
        voter = make_user("v3@example.be", "V3")
        Vote.cast(deal=self.deal, user=voter, value=1)  # 101
        self.assertEqual(Vote.cast(deal=self.deal, user=voter, value=-1), 99)

    def test_recompute_matches_vote_table(self):
        for i in range(5):
            Vote.cast(deal=self.deal, user=make_user(f"r{i}@example.be", f"R{i}"), value=1)
        Deal.objects.filter(pk=self.deal.pk).update(temperature=0)  # compteur corrompu
        self.assertEqual(self.deal.recompute_temperature(), 105)


class SoftDeleteTests(TestCase):
    """Le cœur de la contrainte : désinscrire sans détruire les transactions."""

    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.member = make_user("payeur@example.be", "Payeur")
        cls.plan = Plan.objects.get(code="club-annuel")

    def _pay(self):
        payment, _ = purchase_subscription(
            user=self.member, plan=self.plan, token="tok_demo_visa"
        )
        return payment

    def test_hard_delete_is_blocked_by_payment(self):
        self._pay()
        with self.assertRaises(models.ProtectedError):
            self.member.delete()

    def test_soft_delete_keeps_row_and_payments(self):
        payment = self._pay()
        self.member.soft_delete(reason="test")

        self.member.refresh_from_db()
        self.assertIsNotNone(self.member.deleted_at)
        self.assertFalse(self.member.is_active)
        # La ligne subsiste et la facture reste rattachée.
        self.assertTrue(User.objects.filter(pk=self.member.pk).exists())
        self.assertEqual(Payment.objects.get(pk=payment.pk).user_id, self.member.pk)

    def test_soft_deleted_user_absent_from_active_queryset(self):
        self.member.soft_delete()
        self.assertFalse(User.objects.active().filter(pk=self.member.pk).exists())
        self.assertTrue(User.objects.deleted().filter(pk=self.member.pk).exists())

    def test_anonymise_wipes_pii_but_keeps_key(self):
        payment = self._pay()
        original_pk = self.member.pk
        self.member.anonymise()
        self.member.refresh_from_db()

        self.assertEqual(self.member.pk, original_pk)  # clé invariante
        self.assertNotIn("payeur@example.be", self.member.email)
        self.assertIn("anonymised.dealtrack.invalid", self.member.email)
        self.assertFalse(self.member.has_usable_password())
        self.assertFalse(self.member.marketing_consent)
        self.assertEqual(Payment.objects.get(pk=payment.pk).user_id, original_pk)

    def test_anonymise_implies_soft_delete(self):
        self.member.anonymise()
        self.member.refresh_from_db()
        self.assertIsNotNone(self.member.deleted_at)

    def test_export_contains_expected_sections(self):
        self._pay()
        data = self.member.export_personal_data()
        for key in ("identifiant", "email", "deals_publies", "commentaires", "paiements"):
            self.assertIn(key, data)
        self.assertEqual(len(data["paiements"]), 1)


class PaymentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.member = make_user("client@example.be", "Client")
        cls.plan = Plan.objects.get(code="club-annuel")

    def test_successful_charge_creates_subscription(self):
        payment, subscription = purchase_subscription(
            user=self.member, plan=self.plan, token="tok_demo_visa"
        )
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertIsNotNone(payment.settled_at)
        self.assertIsNotNone(subscription)
        self.assertTrue(subscription.is_current)

    def test_declined_card_records_failure_without_subscription(self):
        payment, subscription = purchase_subscription(
            user=self.member, plan=self.plan, token="tok_demo_fail"
        )
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertIsNone(subscription)

    def test_vat_is_extracted_from_inclusive_amount(self):
        payment, _ = purchase_subscription(
            user=self.member, plan=self.plan, token="tok_demo_visa"
        )
        # 24 € TVAC à 21 % → 24 × 21 / 121 = 4,17 €
        self.assertEqual(payment.vat_amount, Decimal("4.17"))

    def test_invoice_numbering_is_sequential(self):
        first, _ = purchase_subscription(
            user=self.member, plan=self.plan, token="tok_demo_visa"
        )
        other = make_user("client2@example.be", "Client2")
        second, _ = purchase_subscription(user=other, plan=self.plan, token="tok_demo_visa")
        self.assertEqual(
            int(second.reference.split("-")[-1]), int(first.reference.split("-")[-1]) + 1
        )

    def test_invalid_token_refused_before_any_charge(self):
        with self.assertRaises(PaymentError):
            purchase_subscription(user=self.member, plan=self.plan, token="pas-un-jeton")

    def test_closed_account_cannot_pay(self):
        self.member.soft_delete()
        with self.assertRaises(PaymentError):
            purchase_subscription(user=self.member, plan=self.plan, token="tok_demo_visa")

    def test_webhook_signature_is_verified(self):
        gateway = SandboxGateway()
        payload = b'{"type":"payment_intent.succeeded"}'
        import hashlib
        import hmac

        good = hmac.new(b"sandbox-secret", payload, hashlib.sha256).hexdigest()
        self.assertTrue(gateway.verify_webhook(payload, good))
        self.assertFalse(gateway.verify_webhook(payload, "signature-forgee"))


class DealBusinessRuleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed_reference_data()
        cls.author = make_user("redacteur@example.be", "Redacteur")

    def test_discount_percentage_computation(self):
        deal = make_deal(
            self.author, price=Decimal("249.00"), reference_price=Decimal("349.00")
        )
        self.assertEqual(deal.discount_percentage, 29)

    def test_no_discount_without_reference_price(self):
        deal = make_deal(self.author, reference_price=None)
        self.assertIsNone(deal.discount_percentage)

    def test_deal_past_end_date_reads_as_expired(self):
        deal = make_deal(
            self.author,
            status=DealStatus.PUBLISHED,
            published_at=timezone.now() - timezone.timedelta(days=3),
            starts_at=timezone.now() - timezone.timedelta(days=3),
            ends_at=timezone.now() - timezone.timedelta(hours=1),
        )
        self.assertTrue(deal.is_expired)

    def test_visible_queryset_excludes_pending_and_deleted(self):
        make_deal(self.author, status=DealStatus.PENDING)
        published = make_deal(
            self.author, status=DealStatus.PUBLISHED, published_at=timezone.now()
        )
        removed = make_deal(
            self.author, status=DealStatus.PUBLISHED, published_at=timezone.now()
        )
        removed.soft_delete(actor=self.author)

        visible = set(Deal.objects.visible().values_list("pk", flat=True))
        self.assertIn(published.pk, visible)
        self.assertNotIn(removed.pk, visible)
        self.assertEqual(len(visible), 1)

    def test_rejection_requires_reason(self):
        moderator = make_user("modo@example.be", "Modo", role=Role.MODERATOR)
        deal = make_deal(self.author, status=DealStatus.PENDING)
        from apps.moderation.models import ModerationDecision

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ModerationDecision.objects.create(
                    deal=deal,
                    moderator=moderator,
                    decision=ModerationDecision.Decision.REJECTED,
                    reason="",
                )
