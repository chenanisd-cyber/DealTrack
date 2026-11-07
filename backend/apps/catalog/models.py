"""
Référentiels partagés : régions, catégories, marchands.

Trois stratégies de clé primaire cohabitent, chacune justifiée :
  - Region  : code NUTS-1 officiel (BE1/BE2/BE3). Naturel, stable depuis 1988,
              publié par Eurostat. Une clé technique n'apporterait rien.
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


class Region(models.Model):
    """
    Les trois régions belges, identifiées par leur code NUTS-1 Eurostat.

    La Communauté germanophone n'est pas une région : elle fait partie de la
    Wallonie (BE3). Elle est représentée par l'indicateur is_german_speaking
    sur la commune, pas par une quatrième ligne, sous peine de fausser tout
    agrégat régional.
    """

    code = models.CharField(
        _("code NUTS-1"),
        primary_key=True,
        max_length=3,
        validators=[RegexValidator(r"^BE[123]$", _("Codes admis : BE1, BE2, BE3."))],
    )
    name_fr = models.CharField(_("nom (fr)"), max_length=60)
    name_nl = models.CharField(_("nom (nl)"), max_length=60)
    name_de = models.CharField(_("nom (de)"), max_length=60)

    class Meta:
        verbose_name = _("région")
        verbose_name_plural = _("régions")
        ordering = ["code"]

    def __str__(self):
        return self.name_fr

    def label(self, language="fr"):
        return getattr(self, f"name_{language}", self.name_fr)

    @property
    def label_current(self):
        """Libellé dans la langue active. Les gabarits Django ne peuvent pas
        appeler une méthode avec argument, d'où cette propriété."""
        return self.label(get_language() or "fr")


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
