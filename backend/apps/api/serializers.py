"""
Sérialiseurs.

Deux principes tenus partout :
  1. Liste blanche de champs. Jamais `fields = "__all__"` : un champ ajouté au
     modèle demain ne doit pas devenir écrivable par l'API par accident
     (Mass Assignment).
  2. Les champs de décision — statut, auteur, température — sont en lecture
     seule. Ils sont fixés par le serveur, jamais par la charge utile.
"""

from decimal import Decimal

from django.utils.text import slugify
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from apps.accounts.validators import validate_no_control_characters
from apps.catalog.models import Category, Merchant, Region
from apps.deals.models import Comment, Deal, DealStatus, Vote


class RegionSerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()

    class Meta:
        model = Region
        fields = ["code", "label"]

    def get_label(self, obj):
        return obj.label(get_language() or "fr")


class CategorySerializer(serializers.ModelSerializer):
    label = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "slug", "label"]

    def get_label(self, obj):
        return obj.label(get_language() or "fr")


class MerchantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Merchant
        fields = ["id", "name", "slug", "country", "is_local_independent", "is_verified"]
        read_only_fields = ["is_verified"]


class DealListSerializer(serializers.ModelSerializer):
    """Charge utile allégée pour le flux."""

    merchant = MerchantSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    author = serializers.CharField(source="submitted_by.display_name", read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    url = serializers.HyperlinkedIdentityField(view_name="api:deal-detail")

    class Meta:
        model = Deal
        fields = [
            "id",
            "url",
            "title",
            "slug",
            "price",
            "reference_price",
            "currency",
            "discount_percentage",
            "shipping_cost",
            "merchant",
            "category",
            "author",
            "status",
            "temperature",
            "is_cross_border",
            "is_expired",
            "published_at",
            "ends_at",
        ]
        read_only_fields = fields


class DealDetailSerializer(serializers.ModelSerializer):
    merchant = MerchantSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    regions = RegionSerializer(many=True, read_only=True)
    author = serializers.CharField(source="submitted_by.display_name", read_only=True)
    discount_percentage = serializers.IntegerField(read_only=True)
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = Deal
        fields = [
            "id",
            "title",
            "slug",
            "description",
            "external_url",
            "price",
            "reference_price",
            "currency",
            "shipping_cost",
            "discount_percentage",
            "merchant",
            "category",
            "regions",
            "author",
            "language",
            "status",
            "temperature",
            "is_cross_border",
            "starts_at",
            "ends_at",
            "published_at",
            "created_at",
            "comment_count",
        ]
        read_only_fields = fields

    def get_comment_count(self, obj):
        return obj.comments.filter(deleted_at__isnull=True).count()


class DealWriteSerializer(serializers.ModelSerializer):
    """
    Création et modification. Le statut n'est pas exposé : une offre entre
    toujours en file de modération, quelle que soit la charge utile envoyée.
    """

    merchant = serializers.PrimaryKeyRelatedField(queryset=Merchant.objects.all())
    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True)
    )
    regions = serializers.PrimaryKeyRelatedField(
        queryset=Region.objects.all(), many=True, required=False
    )

    class Meta:
        model = Deal
        fields = [
            "id",
            "title",
            "description",
            "external_url",
            "price",
            "reference_price",
            "currency",
            "shipping_cost",
            "merchant",
            "category",
            "regions",
            "language",
            "is_cross_border",
            "starts_at",
            "ends_at",
        ]
        read_only_fields = ["id"]

    # -- Validations de champ -------------------------------------------
    def validate_title(self, value):
        validate_no_control_characters(value)
        cleaned = " ".join(value.split())
        if cleaned.isupper():
            raise serializers.ValidationError(_("Évitez les titres entièrement en majuscules."))
        if cleaned.count("!") > 1:
            raise serializers.ValidationError(_("Un seul point d'exclamation au maximum."))
        return cleaned

    def validate_description(self, value):
        validate_no_control_characters(value)
        return value.strip()

    def validate_external_url(self, value):
        """
        Le lien doit être en HTTPS et pointer vers un hôte, pas vers un schéma
        exotique. Bloque javascript:, data: et les URL relatives protocolaires.
        """
        if not value.lower().startswith("https://"):
            raise serializers.ValidationError(_("Le lien doit être en HTTPS."))
        return value

    def validate_price(self, value):
        if value < Decimal("0"):
            raise serializers.ValidationError(_("Le prix ne peut pas être négatif."))
        if value > Decimal("100000"):
            raise serializers.ValidationError(_("Prix invraisemblable pour un bon plan."))
        return value

    # -- Validations croisées -------------------------------------------
    def validate(self, attrs):
        price = attrs.get("price", getattr(self.instance, "price", None))
        reference = attrs.get(
            "reference_price", getattr(self.instance, "reference_price", None)
        )
        if reference is not None and price is not None and reference <= price:
            raise serializers.ValidationError(
                {
                    "reference_price": _(
                        "Le prix de référence doit dépasser le prix affiché, "
                        "sinon la réduction annoncée est trompeuse."
                    )
                }
            )

        starts = attrs.get("starts_at", getattr(self.instance, "starts_at", None))
        ends = attrs.get("ends_at", getattr(self.instance, "ends_at", None))
        if starts and ends and ends <= starts:
            raise serializers.ValidationError(
                {"ends_at": _("La fin de l'offre doit suivre son début.")}
            )

        merchant = attrs.get("merchant", getattr(self.instance, "merchant", None))
        cross_border = attrs.get(
            "is_cross_border", getattr(self.instance, "is_cross_border", False)
        )
        if merchant and merchant.country != "BE" and not cross_border:
            raise serializers.ValidationError(
                {
                    "is_cross_border": _(
                        "Un marchand hors Belgique impose de cocher « offre transfrontalière »."
                    )
                }
            )
        return attrs

    def create(self, validated):
        regions = validated.pop("regions", [])
        request = self.context["request"]
        deal = Deal.objects.create(
            **validated,
            submitted_by=request.user,
            status=DealStatus.PENDING,  # imposé côté serveur
            slug=self._unique_slug(validated["title"]),
        )
        deal.regions.set(regions)

        from apps.moderation.models import AuditLog

        AuditLog.record(
            action=AuditLog.Action.DEAL_SUBMITTED,
            actor=request.user,
            target=deal,
            request=request,
        )
        return deal

    def update(self, instance, validated):
        regions = validated.pop("regions", None)
        for field, value in validated.items():
            setattr(instance, field, value)
        instance.save()
        if regions is not None:
            instance.regions.set(regions)

        from apps.moderation.models import AuditLog

        AuditLog.record(
            action=AuditLog.Action.DEAL_UPDATED,
            actor=self.context["request"].user,
            target=instance,
            request=self.context["request"],
            metadata={"fields": sorted(validated.keys())},
        )
        return instance

    @staticmethod
    def _unique_slug(title):
        base = slugify(title)[:140] or "deal"
        slug, suffix = base, 1
        while Deal.objects.filter(slug=slug).exists():
            suffix += 1
            slug = f"{base[:150]}-{suffix}"
        return slug


class VoteSerializer(serializers.Serializer):
    value = serializers.ChoiceField(choices=Vote.Value.choices)


class CommentSerializer(serializers.ModelSerializer):
    author = serializers.CharField(source="author.display_name", read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "deal", "author", "body", "is_verified_purchase", "created_at"]
        read_only_fields = ["id", "author", "is_verified_purchase", "created_at"]

    def validate_body(self, value):
        validate_no_control_characters(value)
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError(_("Commentaire trop court."))
        return cleaned

    def create(self, validated):
        return Comment.objects.create(**validated, author=self.context["request"].user)
