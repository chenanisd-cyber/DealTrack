"""
Cœur métier : les offres, les votes et la discussion.

Sur la dénormalisation assumée : Deal.temperature est un compteur entretenu par
une transaction, alors que la source de vérité reste la table Vote. Recalculer
un SUM sur les votes à chaque affichage du flux coûterait une agrégation par
ligne affichée. Le compteur est recalculable à tout moment par la commande
`recompute_temperatures`, ce qui garde la table Vote souveraine.
"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinLengthValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import F, Q, Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from apps.accounts.validators import validate_no_control_characters

TEMPERATURE_BASE = 100  # tout deal publié démarre à 100 °

# Nom de la langue de rédaction, décliné dans la langue de lecture : le badge
# doit dire « Offre rédigée en néerlandais », pas « rédigée en Nederlands ».
LANGUAGE_NAMES = {
    "fr": _("français"),
    "nl": _("néerlandais"),
    "de": _("allemand"),
}


class DealStatus(models.TextChoices):
    DRAFT = "draft", _("Brouillon")
    PENDING = "pending", _("En attente de modération")
    PUBLISHED = "published", _("Publié")
    REJECTED = "rejected", _("Refusé")
    EXPIRED = "expired", _("Expiré")


class DealQuerySet(models.QuerySet):
    def visible(self):
        """Ce qu'un visiteur non authentifié a le droit de voir."""
        return self.filter(
            status__in=[DealStatus.PUBLISHED, DealStatus.EXPIRED],
            deleted_at__isnull=True,
        )

    def live(self):
        return self.filter(status=DealStatus.PUBLISHED, deleted_at__isnull=True)

    def for_user(self, user):
        """
        Filtre d'accès unique, appliqué aussi bien par les vues HTML que par
        l'API. Centraliser évite qu'un point d'entrée oublie une condition.
        """
        if not user or not user.is_authenticated:
            return self.visible()
        if user.is_moderator:
            return self.filter(deleted_at__isnull=True)
        return self.filter(
            Q(status__in=[DealStatus.PUBLISHED, DealStatus.EXPIRED]) | Q(submitted_by=user),
            deleted_at__isnull=True,
        )


class Deal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    title = models.CharField(
        _("titre"),
        max_length=140,
        validators=[MinLengthValidator(15), validate_no_control_characters],
    )
    slug = models.SlugField(_("identifiant d'URL"), max_length=160, unique=True)
    description = models.TextField(
        _("description"),
        max_length=4000,
        validators=[MinLengthValidator(30), validate_no_control_characters],
    )
    external_url = models.URLField(_("lien vers l'offre"), max_length=600)

    price = models.DecimalField(
        _("prix"),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    reference_price = models.DecimalField(
        _("prix de référence"),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text=_(
            "Prix le plus bas pratiqué par le marchand durant les 30 jours "
            "précédents (Code de droit économique, art. VI.18)."
        ),
    )
    currency = models.CharField(_("devise"), max_length=3, default="EUR")
    shipping_cost = models.DecimalField(
        _("frais de livraison"),
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    merchant = models.ForeignKey(
        "catalog.Merchant",
        verbose_name=_("marchand"),
        on_delete=models.PROTECT,
        related_name="deals",
    )
    category = models.ForeignKey(
        "catalog.Category",
        verbose_name=_("catégorie"),
        on_delete=models.PROTECT,
        related_name="deals",
    )
    regions = models.ManyToManyField(
        "catalog.Region",
        verbose_name=_("régions concernées"),
        related_name="deals",
        blank=True,
    )
    # PROTECT : un membre qui a publié des deals ne peut pas être effacé sans
    # que ses contributions le soient d'abord. C'est voulu — la modération doit
    # pouvoir remonter à l'auteur d'une offre litigieuse.
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_("auteur"),
        on_delete=models.PROTECT,
        related_name="submitted_deals",
    )

    status = models.CharField(
        _("statut"),
        max_length=20,
        choices=DealStatus.choices,
        default=DealStatus.PENDING,
        db_index=True,
    )
    is_cross_border = models.BooleanField(_("offre transfrontalière"), default=False)
    language = models.CharField(
        _("langue de rédaction"), max_length=5, choices=settings.LANGUAGES, default="fr"
    )

    starts_at = models.DateTimeField(_("début"), default=timezone.now)
    ends_at = models.DateTimeField(_("fin"), null=True, blank=True)
    published_at = models.DateTimeField(_("publié le"), null=True, blank=True, db_index=True)

    temperature = models.IntegerField(
        _("température"),
        default=TEMPERATURE_BASE,
        db_index=True,
        help_text=_("Compteur dérivé de la table Vote, recalculable."),
    )
    created_at = models.DateTimeField(_("créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("modifié le"), auto_now=True)
    deleted_at = models.DateTimeField(_("retiré le"), null=True, blank=True, db_index=True)

    objects = DealQuerySet.as_manager()

    class Meta:
        verbose_name = _("deal")
        verbose_name_plural = _("deals")
        ordering = ["-temperature", "-published_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=0), name="deal_price_non_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(shipping_cost__gte=0), name="deal_shipping_non_negative"
            ),
            # Un prix barré doit être supérieur au prix affiché, sans quoi la
            # réduction annoncée est mensongère.
            models.CheckConstraint(
                condition=models.Q(reference_price__isnull=True)
                | models.Q(reference_price__gt=models.F("price")),
                name="deal_reference_price_above_price",
            ),
            models.CheckConstraint(
                condition=models.Q(ends_at__isnull=True)
                | models.Q(ends_at__gt=models.F("starts_at")),
                name="deal_ends_after_start",
            ),
            # Publié implique daté : sans cela le tri chronologique est faussé.
            models.CheckConstraint(
                condition=~models.Q(status="published") | models.Q(published_at__isnull=False),
                name="deal_published_requires_date",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "-published_at"], name="deal_status_pub_idx"),
            models.Index(fields=["merchant", "status"], name="deal_merchant_status_idx"),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("deals:detail", kwargs={"slug": self.slug})

    # -- Règles métier ---------------------------------------------------
    @property
    def discount_percentage(self):
        if not self.reference_price or self.reference_price <= 0:
            return None
        return int(round((1 - self.price / self.reference_price) * 100))

    @property
    def is_expired(self):
        if self.status == DealStatus.EXPIRED:
            return True
        return bool(self.ends_at and self.ends_at <= timezone.now())

    @property
    def is_free_shipping(self):
        return self.shipping_cost == 0

    # -- Contenu multilingue ---------------------------------------------
    def _translation(self, language):
        """
        Traduction dans la langue demandée, cherchée en Python.

        L'itération sur `self.translations.all()` consomme le cache posé par
        `prefetch_related("translations")`. Un `.filter(language=...)` le
        contournerait et relancerait une requête par deal affiché : dix
        requêtes supplémentaires par page de flux, vingt avec le rail latéral.
        """
        for translation in self.translations.all():
            if translation.language == language:
                return translation
        return None

    @property
    def title_current(self):
        """Titre dans la langue active, avec repli sur le texte d'origine."""
        translation = self._translation(get_language() or "fr")
        return translation.title if translation else self.title

    @property
    def description_current(self):
        translation = self._translation(get_language() or "fr")
        return translation.description if translation else self.description

    @property
    def is_translated(self):
        """
        Vrai si le visiteur lit bien le contenu dans la langue de la page —
        soit parce que l'offre y a été rédigée, soit parce qu'une traduction
        existe. Faux : le gabarit affiche le texte d'origine et le signale.
        """
        language = get_language() or "fr"
        return self.language == language or self._translation(language) is not None

    @property
    def source_language_label(self):
        """Nom de la langue de rédaction, pour le badge de repli."""
        return LANGUAGE_NAMES.get(self.language, self.language)

    def publish(self, *, moderator, reason=""):
        from apps.moderation.models import AuditLog, ModerationDecision

        self.status = DealStatus.PUBLISHED
        self.published_at = self.published_at or timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])
        ModerationDecision.objects.create(
            deal=self,
            moderator=moderator,
            decision=ModerationDecision.Decision.APPROVED,
            reason=reason,
        )
        AuditLog.record(actor=moderator, action=AuditLog.Action.DEAL_PUBLISHED, target=self)
        return self

    def reject(self, *, moderator, reason):
        from apps.moderation.models import AuditLog, ModerationDecision

        self.status = DealStatus.REJECTED
        self.save(update_fields=["status", "updated_at"])
        ModerationDecision.objects.create(
            deal=self,
            moderator=moderator,
            decision=ModerationDecision.Decision.REJECTED,
            reason=reason,
        )
        AuditLog.record(
            actor=moderator,
            action=AuditLog.Action.DEAL_REJECTED,
            target=self,
            metadata={"reason": reason},
        )
        return self

    def soft_delete(self, *, actor):
        """Retire l'offre du flux sans casser les votes ni les commentaires."""
        from apps.moderation.models import AuditLog

        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])
        AuditLog.record(actor=actor, action=AuditLog.Action.DEAL_DELETED, target=self)
        return self

    def recompute_temperature(self):
        total = self.votes.aggregate(s=Sum("value"))["s"] or 0
        Deal.objects.filter(pk=self.pk).update(temperature=TEMPERATURE_BASE + total)
        self.refresh_from_db(fields=["temperature"])
        return self.temperature


class DealTranslation(models.Model):
    """
    Titre et description d'une offre dans une autre langue.

    Même choix que CategoryTranslation : une ligne par langue plutôt que des
    colonnes title_fr / title_nl / title_de. Une quatrième langue devient une
    insertion de données au lieu d'une migration de schéma, les offres non
    traduites ne paient pas trois colonnes vides, et l'unicité (deal, langue)
    est garantie par la base.

    is_machine_translated distingue la traduction relue d'une sortie de moteur
    automatique : le flux belge annonce des prix et des conditions de garantie,
    une machine ne doit pas pouvoir les reformuler sans que ce soit visible.
    """

    id = models.BigAutoField(primary_key=True)
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="translations")
    language = models.CharField(_("langue"), max_length=5, choices=settings.LANGUAGES)
    title = models.CharField(
        _("titre"),
        max_length=140,
        validators=[MinLengthValidator(15), validate_no_control_characters],
    )
    description = models.TextField(
        _("description"),
        max_length=4000,
        validators=[MinLengthValidator(30), validate_no_control_characters],
    )
    is_machine_translated = models.BooleanField(
        _("traduction automatique"),
        default=False,
        help_text=_("À cocher tant qu'un humain n'a pas relu le texte."),
    )

    class Meta:
        verbose_name = _("traduction de deal")
        verbose_name_plural = _("traductions de deal")
        ordering = ["language"]
        constraints = [
            models.UniqueConstraint(fields=["deal", "language"], name="uniq_deal_language")
        ]

    def __str__(self):
        return f"{self.deal.slug} [{self.language}]"


class Vote(models.Model):
    """
    Un vote par membre et par deal. La contrainte d'unicité est portée par la
    base : c'est la seule couche que deux requêtes concurrentes ne peuvent pas
    contourner.
    """

    class Value(models.IntegerChoices):
        COLD = -1, _("Refroidir")
        HOT = 1, _("Réchauffer")

    id = models.BigAutoField(primary_key=True)
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="votes"
    )
    value = models.SmallIntegerField(_("sens du vote"), choices=Value.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("vote")
        verbose_name_plural = _("votes")
        constraints = [
            models.UniqueConstraint(fields=["deal", "user"], name="uniq_vote_per_user_deal"),
            models.CheckConstraint(
                condition=models.Q(value__in=[-1, 1]), name="vote_value_is_minus_one_or_one"
            ),
        ]

    def __str__(self):
        return f"{self.user} {self.value:+d} {self.deal}"

    @classmethod
    @transaction.atomic
    def cast(cls, *, deal, user, value):
        """
        Enregistre un vote ou l'annule si l'utilisateur revote dans le même sens.
        Le compteur est mis à jour par F() : pas de lecture-modification-écriture,
        donc pas de perte de vote entre deux requêtes simultanées.
        """
        existing = cls.objects.select_for_update().filter(deal=deal, user=user).first()

        if existing is None:
            cls.objects.create(deal=deal, user=user, value=value)
            delta = value
        elif existing.value == value:
            existing.delete()
            delta = -value
        else:
            delta = value - existing.value
            existing.value = value
            existing.save(update_fields=["value", "updated_at"])

        Deal.objects.filter(pk=deal.pk).update(temperature=F("temperature") + delta)
        deal.refresh_from_db(fields=["temperature"])
        return deal.temperature


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="comments"
    )
    body = models.TextField(
        _("commentaire"),
        max_length=2000,
        validators=[MinLengthValidator(2), validate_no_control_characters],
    )
    is_verified_purchase = models.BooleanField(_("achat confirmé"), default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    deleted_at = models.DateTimeField(_("supprimé le"), null=True, blank=True)

    class Meta:
        verbose_name = _("commentaire")
        verbose_name_plural = _("commentaires")
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author} sur {self.deal}"

    def soft_delete(self, *, actor):
        from apps.moderation.models import AuditLog

        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at"])
        AuditLog.record(actor=actor, action=AuditLog.Action.COMMENT_DELETED, target=self)


class Alert(models.Model):
    """Alerte par mot-clé : la fonctionnalité « ne rien manquer » du projet."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alerts"
    )
    keyword = models.CharField(_("mot-clé"), max_length=80, validators=[MinLengthValidator(2)])
    category = models.ForeignKey(
        "catalog.Category", on_delete=models.CASCADE, null=True, blank=True
    )
    region = models.ForeignKey(
        "catalog.Region", on_delete=models.PROTECT, null=True, blank=True
    )
    max_price = models.DecimalField(
        _("prix maximum"), max_digits=10, decimal_places=2, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("alerte")
        verbose_name_plural = _("alertes")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "keyword", "category", "region"],
                name="uniq_alert_per_user_criteria",
            ),
            models.CheckConstraint(
                condition=models.Q(max_price__isnull=True) | models.Q(max_price__gt=0),
                name="alert_max_price_positive",
            ),
        ]

    def __str__(self):
        return f"{self.user} · {self.keyword}"
