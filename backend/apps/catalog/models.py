"""
Référentiels partagés : catégories, marchands.

Trois stratégies de clé primaire cohabitent, chacune justifiée :
  - Category: UUID. Le slug est traduit et peut être réécrit pour le
              référencement, donc il ne peut pas servir de clé.
  - Merchant: UUID. Le nom commercial et le numéro de TVA changent lors des
              fusions ; ni l'un ni l'autre n'est invariant.
"""

import uuid

from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from apps.accounts.validators import validate_be_vat, validate_no_control_characters

from .images import IMAGE_VALIDATORS, merchant_logo_path


class Category(models.Model):
    """Arbre de catégories sur un seul niveau de profondeur en pratique."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(_("identifiant d'URL"), max_length=60, unique=True)
    parent = models.ForeignKey(
        "self",
        verbose_name=_("catégorie parente"),
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    position = models.PositiveSmallIntegerField(_("ordre d'affichage"), default=0)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        verbose_name = _("catégorie")
        verbose_name_plural = _("catégories")
        ordering = ["position", "slug"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(parent=models.F("id")),
                name="category_no_self_parent",
            ),
        ]

    def __str__(self):
        return self.slug

    def label(self, language="fr"):
        """Libellé traduit, avec repli sur le français puis sur le slug."""
        translations = {t.language: t.name for t in self.translations.all()}
        return translations.get(language) or translations.get("fr") or self.slug

    @property
    def label_current(self):
        return self.label(get_language() or "fr")


class CategoryTranslation(models.Model):
    """
    Libellés de catégorie, une ligne par langue.

    Table séparée plutôt que colonnes name_fr / name_nl / name_de : ajouter une
    quatrième langue devient une insertion de données au lieu d'une migration
    de schéma, et l'unicité (catégorie, langue) est garantie par la base.
    """

    id = models.BigAutoField(primary_key=True)
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="translations"
    )
    language = models.CharField(_("langue"), max_length=5)
    name = models.CharField(_("libellé"), max_length=80, validators=[MinLengthValidator(2)])

    class Meta:
        verbose_name = _("libellé de catégorie")
        verbose_name_plural = _("libellés de catégorie")
        constraints = [
            models.UniqueConstraint(
                fields=["category", "language"], name="uniq_category_language"
            )
        ]

    def __str__(self):
        return f"{self.category.slug} [{self.language}]"


# Types de commerce OpenStreetMap (clé « shop ») retenus pour l'annuaire.
SHOP_TYPES = {
    "bakery": _("Boulangerie"),
    "pastry": _("Pâtisserie"),
    "butcher": _("Boucherie"),
    "cheese": _("Fromagerie"),
    "deli": _("Épicerie fine"),
    "greengrocer": _("Primeur"),
    "wine": _("Caviste"),
    "coffee": _("Café et torréfaction"),
    "chocolate": _("Chocolatier"),
    "books": _("Librairie"),
    "bicycle": _("Vélos"),
}


class Merchant(models.Model):
    """
    Enseigne chez qui le deal est disponible.

    L'indicateur is_local_independent porte la promesse « commerçant local » du
    projet : il ne se déduit pas du pays, une filiale belge d'un groupe
    international n'étant pas un indépendant.
    """

    class Country(models.TextChoices):
        BE = "BE", _("Belgique")
        NL = "NL", _("Pays-Bas")
        FR = "FR", _("France")
        DE = "DE", _("Allemagne")
        LU = "LU", _("Luxembourg")
        OTHER = "ZZ", _("Autre pays")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        _("enseigne"), max_length=120, validators=[validate_no_control_characters]
    )
    slug = models.SlugField(_("identifiant d'URL"), max_length=120, unique=True)
    country = models.CharField(
        _("pays"), max_length=2, choices=Country.choices, default=Country.BE, db_index=True
    )
    website = models.URLField(_("site web"), max_length=300, blank=True)
    vat_number = models.CharField(
        _("numéro de TVA"),
        max_length=20,
        blank=True,
        validators=[validate_be_vat],
        help_text=_("Format belge uniquement, contrôlé par sa clé modulo 97."),
    )
    is_local_independent = models.BooleanField(
        _("commerçant indépendant belge"),
        default=False,
        help_text=_("Déclenche le badge « Commerçant local » dans le flux."),
    )
    is_verified = models.BooleanField(
        _("enseigne vérifiée"),
        default=False,
        help_text=_("Vérifiée par la modération : identité et site marchand contrôlés."),
    )
    # Identité visuelle : affichée quand une offre n'a pas de photo.
    logo = models.ImageField(
        _("logo"),
        upload_to=merchant_logo_path,
        blank=True,
        validators=IMAGE_VALIDATORS,
        help_text=_("JPEG, PNG ou WebP, 2 Mo maximum."),
    )
    brand_color = models.CharField(
        _("couleur de l'enseigne"),
        max_length=7,
        default="#01182B",
        validators=[
            RegexValidator(r"^#[0-9A-Fa-f]{6}$", _("Couleur hexadécimale, ex. #0090E3."))
        ],
        help_text=_("Fond de la vignette affichée à la place de la photo."),
    )
    # -- Commerçants locaux (annuaire alimenté par OpenStreetMap) -----------
    shop_type = models.CharField(
        _("type de commerce"), max_length=30, blank=True, help_text=_("Valeur OSM « shop ».")
    )
    address = models.CharField(_("adresse"), max_length=200, blank=True)
    city = models.CharField(_("ville"), max_length=80, blank=True, db_index=True)
    latitude = models.DecimalField(
        _("latitude"), max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        _("longitude"), max_digits=9, decimal_places=6, null=True, blank=True
    )
    osm_id = models.BigIntegerField(
        _("identifiant OpenStreetMap"),
        null=True,
        blank=True,
        unique=True,
        help_text=_("Évite les doublons lors d'un nouvel import."),
    )
    created_at = models.DateTimeField(_("créée le"), auto_now_add=True)

    class Meta:
        verbose_name = _("marchand")
        verbose_name_plural = _("marchands")
        ordering = ["name"]
        constraints = [
            # Un indépendant belge est nécessairement établi en Belgique.
            models.CheckConstraint(
                condition=models.Q(is_local_independent=False) | models.Q(country="BE"),
                name="merchant_local_implies_be",
            ),
            # Un numéro de TVA belge ne peut être porté que par une entité belge.
            models.CheckConstraint(
                condition=models.Q(vat_number="") | models.Q(country="BE"),
                name="merchant_vat_implies_be",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def shop_type_label(self):
        return SHOP_TYPES.get(self.shop_type, "")

    @property
    def osm_url(self):
        return f"https://www.openstreetmap.org/node/{self.osm_id}" if self.osm_id else ""

    @property
    def brand_text_color(self):
        """Texte blanc sur fond sombre, bleu nuit sur fond clair (contraste WCAG)."""
        red, green, blue = (int(self.brand_color[i : i + 2], 16) for i in (1, 3, 5))
        luminance = 0.299 * red + 0.587 * green + 0.114 * blue
        return "#01182B" if luminance > 160 else "#FFFFFF"


class MerchantAccount(models.Model):
    """
    Lien entre un membre et le commerce qu'il gère : c'est la clé de
    l'« espace commerçant ».

    Le membre demande à gérer une fiche ; la modération vérifie qu'il s'agit
    bien du commerçant, puis accepte ou refuse. Tant que la demande n'est pas
    acceptée, elle n'ouvre aucun droit : sans ce contrôle, n'importe qui
    pourrait modifier la fiche d'un concurrent.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("En attente")
        APPROVED = "approved", _("Acceptée")
        REJECTED = "rejected", _("Refusée")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="merchant_accounts",
        verbose_name=_("membre"),
    )
    merchant = models.ForeignKey(
        Merchant,
        on_delete=models.CASCADE,
        related_name="accounts",
        verbose_name=_("commerce"),
    )
    status = models.CharField(
        _("statut"),
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    message = models.CharField(
        _("justification"),
        max_length=300,
        validators=[MinLengthValidator(10), validate_no_control_characters],
        help_text=_("Ce qui prouve le lien avec le commerce : fonction, numéro de TVA…"),
    )
    created_at = models.DateTimeField(_("demandée le"), auto_now_add=True)
    decided_at = models.DateTimeField(_("traitée le"), null=True, blank=True)
    decided_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("traitée par"),
    )

    class Meta:
        verbose_name = _("compte commerçant")
        verbose_name_plural = _("comptes commerçants")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "merchant"], name="uniq_merchant_account_per_user"
            ),
            # Une demande acceptée ou refusée est datée.
            models.CheckConstraint(
                condition=models.Q(status="pending") | models.Q(decided_at__isnull=False),
                name="merchant_account_decided_requires_date",
            ),
        ]

    def __str__(self):
        return f"{self.user} → {self.merchant} ({self.get_status_display()})"

    def decide(self, *, moderator, approve):
        """Accepte ou refuse la demande, et trace la décision."""
        from django.utils import timezone

        from apps.moderation.models import AuditLog

        self.status = self.Status.APPROVED if approve else self.Status.REJECTED
        self.decided_at = timezone.now()
        self.decided_by = moderator
        self.save(update_fields=["status", "decided_at", "decided_by"])
        AuditLog.record(
            actor=moderator,
            action=AuditLog.Action.MERCHANT_CLAIM_DECIDED,
            target=self.merchant,
            metadata={"member": str(self.user_id), "approved": approve},
        )
        return self
