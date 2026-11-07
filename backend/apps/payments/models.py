"""
Paiement de l'abonnement « Club ».

Le point structurant : Payment.user est en on_delete=PROTECT. Supprimer un
membre qui a payé lève ProtectedError, et c'est le comportement recherché —
l'article 315 du Code des impôts sur les revenus impose de conserver les pièces
justificatives sept ans. La désinscription passe donc obligatoirement par
User.soft_delete() puis User.anonymise().

Aucune donnée de carte n'est stockée ni même reçue : le navigateur échange les
coordonnées bancaires contre un jeton chez le prestataire, et le serveur ne
manipule que ce jeton. Cela maintient l'application hors du périmètre PCI-DSS
le plus lourd (SAQ-A).
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _


class Plan(models.Model):
    """Formule d'abonnement. Le prix est historisé sur le paiement, pas ici."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(_("code"), max_length=30, unique=True)
    name_fr = models.CharField(max_length=80)
    name_nl = models.CharField(max_length=80)
    name_de = models.CharField(max_length=80)
    price = models.DecimalField(
        _("prix TVAC"),
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    vat_rate = models.DecimalField(
        _("taux de TVA"),
        max_digits=4,
        decimal_places=2,
        default=Decimal("21.00"),
        help_text=_("Taux belge standard : 21 %."),
    )
    duration_days = models.PositiveSmallIntegerField(_("durée en jours"), default=365)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("formule")
        verbose_name_plural = _("formules")
        ordering = ["price"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=0), name="plan_price_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(duration_days__gt=0), name="plan_duration_positive"
            ),
        ]

    def __str__(self):
        return self.name_fr

    def label(self, language="fr"):
        return getattr(self, f"name_{language}", self.name_fr)

    @property
    def label_current(self):
        return self.label(get_language() or "fr")


class Payment(models.Model):
    """
    Transaction. Immuable une fois aboutie : un remboursement crée une nouvelle
    ligne de sens inverse plutôt que de réécrire l'originale, comme en
    comptabilité en partie double.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("En attente")
        SUCCEEDED = "succeeded", _("Réussi")
        FAILED = "failed", _("Échoué")
        REFUNDED = "refunded", _("Remboursé")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Numéro de facture séquentiel, exigé par l'administration fiscale belge :
    # continu, sans trou, dans l'ordre chronologique.
    reference = models.CharField(
        _("référence de facture"),
        max_length=30,
        unique=True,
        help_text=_("Format DT-AAAA-NNNNNN, séquentiel et sans rupture."),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("membre"),
        on_delete=models.PROTECT,  # ← verrou de conservation comptable
        related_name="payments",
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="payments")

    amount = models.DecimalField(
        _("montant TVAC"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    vat_amount = models.DecimalField(_("dont TVA"), max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="EUR")

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    gateway = models.CharField(_("prestataire"), max_length=30, default="sandbox")
    gateway_reference = models.CharField(
        _("référence prestataire"),
        max_length=120,
        unique=True,
        help_text=_("Identifiant côté prestataire. Unique : garantit l'idempotence."),
    )
    # Conservé pour le rapprochement bancaire et l'affichage « •••• 4242 ».
    card_last4 = models.CharField(max_length=4, blank=True)
    card_brand = models.CharField(max_length=20, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    settled_at = models.DateTimeField(_("réglé le"), null=True, blank=True)

    class Meta:
        verbose_name = _("paiement")
        verbose_name_plural = _("paiements")
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0), name="payment_amount_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(vat_amount__gte=0)
                & models.Q(vat_amount__lte=models.F("amount")),
                name="payment_vat_within_amount",
            ),
            # Un paiement abouti est nécessairement daté.
            models.CheckConstraint(
                condition=~models.Q(status="succeeded") | models.Q(settled_at__isnull=False),
                name="payment_succeeded_requires_settled_at",
            ),
        ]
        indexes = [models.Index(fields=["user", "-created_at"], name="payment_user_date_idx")]

    def __str__(self):
        return f"{self.reference} · {self.amount} {self.currency}"

    @staticmethod
    def next_reference():
        """Numérotation continue par exercice comptable."""
        year = timezone.now().year
        last = (
            Payment.objects.filter(reference__startswith=f"DT-{year}-")
            .order_by("-reference")
            .values_list("reference", flat=True)
            .first()
        )
        nxt = int(last.split("-")[-1]) + 1 if last else 1
        return f"DT-{year}-{nxt:06d}"


class Subscription(models.Model):
    """Adhésion Club active, dérivée d'un paiement abouti."""

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        EXPIRED = "expired", _("Expirée")
        CANCELLED = "cancelled", _("Résiliée")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="subscriptions"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    payment = models.OneToOneField(
        Payment, on_delete=models.PROTECT, related_name="subscription"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    started_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("abonnement")
        verbose_name_plural = _("abonnements")
        ordering = ["-started_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("started_at")),
                name="subscription_ends_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.user} · {self.plan.code}"

    @property
    def is_current(self):
        return self.status == self.Status.ACTIVE and self.ends_at > timezone.now()
