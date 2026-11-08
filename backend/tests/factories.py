"""Fabriques partagées par les tests. Aucune dépendance externe."""

from decimal import Decimal

from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import Role, User
from apps.catalog.models import Category, CategoryTranslation, Merchant
from apps.deals.models import Deal, DealStatus
from apps.payments.models import Plan

STRONG_PASSWORD = "Tram-81-Vers-Ixelles"
_counter = {"n": 0}


def seed_reference_data():
    """Référentiels minimaux : une catégorie, un marchand, deux formules."""

    category, _ = Category.objects.update_or_create(slug="high-tech", defaults={"position": 0})
    for lang, name in [("fr", "High-tech"), ("nl", "Elektronica"), ("de", "Elektronik")]:
        CategoryTranslation.objects.update_or_create(
            category=category, language=lang, defaults={"name": name}
        )

    Merchant.objects.update_or_create(
        slug="coolblue",
        defaults={
            "name": "Coolblue",
            "country": "BE",
            "is_verified": True,
            "vat_number": "BE0673617277",
        },
    )
    Merchant.objects.update_or_create(
        slug="action-maastricht",
        defaults={"name": "Action Maastricht", "country": "NL"},
    )
    Plan.objects.update_or_create(
        code="vip-annuel",
        defaults={
            "name_fr": "VIP annuel",
            "name_nl": "VIP jaarlijks",
            "name_de": "VIP jährlich",
            "price": Decimal("24.00"),
            "vat_rate": Decimal("21.00"),
            "duration_days": 365,
        },
    )
    Plan.objects.update_or_create(
        code="vip-mensuel",
        defaults={
            "name_fr": "VIP mensuel",
            "name_nl": "VIP maandelijks",
            "name_de": "VIP monatlich",
            "price": Decimal("2.50"),
            "vat_rate": Decimal("21.00"),
            "duration_days": 30,
        },
    )


def make_user(email, display_name, *, role=Role.MEMBER, password=STRONG_PASSWORD, **extra):
    user = User(
        email=email,
        display_name=display_name,
        role=role,
        accepted_terms_at=timezone.now(),
        is_staff=role in (Role.MODERATOR, Role.ADMIN),
        **extra,
    )
    user.set_password(password)
    user.save()
    return user


def make_merchant(name="Krëfel", country="BE", **extra):
    return Merchant.objects.create(name=name, slug=slugify(name), country=country, **extra)


def make_deal(author, **overrides):
    _counter["n"] += 1
    n = _counter["n"]
    defaults = {
        "title": f"Casque audio à réduction de bruit, modèle numéro {n}",
        "slug": f"casque-audio-{n}",
        "description": (
            "Description de test suffisamment longue pour satisfaire la longueur "
            "minimale imposée par le modèle, avec des détails plausibles."
        ),
        "external_url": "https://www.coolblue.be/fr/produit/test",
        "price": Decimal("249.00"),
        "reference_price": Decimal("349.00"),
        "shipping_cost": Decimal("0.00"),
        "merchant": Merchant.objects.get(slug="coolblue"),
        "category": Category.objects.get(slug="high-tech"),
        "submitted_by": author,
        "status": DealStatus.PENDING,
        "starts_at": timezone.now(),
    }
    defaults.update(overrides)
    if defaults["status"] in (DealStatus.PUBLISHED,) and "published_at" not in overrides:
        defaults["published_at"] = timezone.now()
    return Deal.objects.create(**defaults)
