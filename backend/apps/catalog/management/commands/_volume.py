"""
Volume du jeu de démonstration : au moins 100 lignes par table métier.

Exigence du dossier (« DUMP de la base de données ») : de vraies données de
test, pas de lorem ipsum, 100 lignes minimum par table sauf les tables
naturellement limitées (catégories, formules d'abonnement).

D'où viennent les données ?
- Offres : 117 vraies promotions relevées sur coolblue.be le 7 novembre 2026
  (titre, prix, prix barré, lien, photos) — fichier data/coolblue.json.
- Commerçants locaux : 120 commerces indépendants réels issus d'OpenStreetMap
  (licence ODbL) — fichier data/osm_shops.json.
- Membres : 110 comptes fictifs aux noms belges courants (adresses
  @example.be, domaine réservé aux exemples : aucun courriel réel).
- Commentaires, signalements, alertes, paiements : générés à partir de
  phrases réalistes rédigées en français, néerlandais et allemand.

Le module ne contient pas de commande : le préfixe « _ » empêche Django de
le prendre pour une commande de gestion. seed_demo l'appelle.
"""

import json
import os
import random
import unicodedata
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.hashers import make_password
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import Role, User
from apps.catalog.models import Merchant
from apps.deals.models import (
    Alert,
    Comment,
    CommentTranslation,
    Deal,
    DealImage,
    DealStatus,
    DealTranslation,
)
from apps.moderation.models import AuditLog, ModerationDecision, Report
from apps.payments.models import Payment, Plan, Subscription

DATA = Path(__file__).resolve().parent / "data"
# Mot de passe des comptes de démonstration. En ligne (Render), DEMO_PASSWORD
# le remplace par un secret : celui du README ne donne alors accès à rien.
PASSWORD = os.environ.get("DEMO_PASSWORD") or "Demo-Tracker-2025"

# -- Membres ----------------------------------------------------------------------
FIRST_NAMES = {
    "fr": [
        "Lucas",
        "Louis",
        "Hugo",
        "Arthur",
        "Nathan",
        "Emma",
        "Léa",
        "Chloé",
        "Manon",
        "Camille",
        "Julie",
        "Sarah",
        "Thomas",
        "Maxime",
        "Antoine",
        "Julien",
        "Céline",
        "Laura",
        "Pauline",
        "Inès",
        "Noah",
        "Zoé",
        "Clara",
        "Romain",
        "Aurélie",
    ],
    "nl": [
        "Lars",
        "Wout",
        "Jens",
        "Pieter",
        "Thijs",
        "Lotte",
        "Fien",
        "Noor",
        "Lien",
        "Hanne",
        "Ruben",
        "Bram",
        "Sander",
        "Stijn",
        "Elke",
        "Leen",
        "Wim",
        "Joke",
        "Kobe",
        "Jef",
        "Ine",
        "Tom",
        "Anouk",
        "Seppe",
    ],
    "de": [
        "Lukas",
        "Jonas",
        "Felix",
        "Anna",
        "Lena",
        "Leonie",
        "Paul",
        "Tim",
        "Marie",
        "Sophie",
    ],
}
LAST_NAMES = {
    "fr": [
        "Dubois",
        "Lambert",
        "Dupont",
        "Martin",
        "Simon",
        "Laurent",
        "Leclercq",
        "Lejeune",
        "Renard",
        "Lemaire",
        "Fontaine",
        "Collignon",
        "Mathieu",
        "François",
        "Henrard",
        "Lecomte",
        "Denis",
        "Gilson",
    ],
    "nl": [
        "Peeters",
        "Janssens",
        "Maes",
        "Jacobs",
        "Mertens",
        "Willems",
        "Claes",
        "Goossens",
        "Wouters",
        "De Smet",
        "Hermans",
        "Michiels",
        "Vermeulen",
        "Van den Broeck",
        "De Backer",
        "Verhoeven",
    ],
    "de": ["Schmitz", "Kessler", "Lentz", "Heinen", "Mreyen", "Cremer", "Pauels", "Brüls"],
}
# (langue, nombre de membres)
MEMBER_GROUPS = [("fr", 50), ("nl", 45), ("de", 15)]


def _ascii(text):
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


def members():
    """110 membres supplémentaires, créés une seule fois (clé : l'adresse e-mail)."""
    password_hash = make_password(PASSWORD)  # haché une fois : Argon2 est lent exprès
    created_users, number = [], 0
    for language, count in MEMBER_GROUPS:
        firsts, lasts = FIRST_NAMES[language], LAST_NAMES[language]
        for i in range(count):
            number += 1
            first = firsts[i % len(firsts)]
            last = lasts[(i * 7 + i // len(firsts)) % len(lasts)]
            local = _ascii(f"{first}.{last}").lower().replace(" ", "")
            user, _ = User.objects.get_or_create(
                email=f"{local}{number}@example.be",
                defaults={
                    "display_name": _ascii(f"{first}{last.replace(' ', '')[:3]}{number}"),
                    "preferred_language": language,
                    "role": Role.MEMBER,
                    "password": password_hash,
                    "accepted_terms_at": timezone.now()
                    - timedelta(days=random.randint(5, 700)),
                    "marketing_consent": random.random() < 0.4,
                    "date_joined": timezone.now() - timedelta(days=random.randint(5, 700)),
                },
            )
            created_users.append(user)
    return created_users


# -- Commerçants locaux (OpenStreetMap) ------------------------------------------
def osm_merchants():
    from apps.catalog.management.commands.import_local_merchants import SHOP_COLORS

    shops = json.loads((DATA / "osm_shops.json").read_text(encoding="utf-8"))
    for shop in shops:
        Merchant.objects.update_or_create(
            osm_id=shop["osm_id"],
            defaults={
                "name": shop["name"],
                "country": "BE",
                "shop_type": shop["shop"],
                "address": shop["address"],
                "city": shop["city"],
                "latitude": Decimal(str(shop["lat"])),
                "longitude": Decimal(str(shop["lon"])),
                "website": shop["website"],
                "is_local_independent": True,
                "is_verified": False,
                "brand_color": SHOP_COLORS.get(shop["shop"], "#01182B"),
            },
            create_defaults={
                "name": shop["name"],
                "slug": f"{slugify(shop['name'])[:100] or 'commerce'}-{shop['osm_id']}",
                "country": "BE",
                "shop_type": shop["shop"],
                "address": shop["address"],
                "city": shop["city"],
                "latitude": Decimal(str(shop["lat"])),
                "longitude": Decimal(str(shop["lon"])),
                "website": shop["website"],
                "is_local_independent": True,
                "is_verified": False,
                "brand_color": SHOP_COLORS.get(shop["shop"], "#01182B"),
            },
        )
    return len(shops)


# -- Offres Coolblue ---------------------------------------------------------------
HIGH_TECH = {"tv", "laptop", "phone", "tablet", "soundbar", "watch"}
TEMPLATES = {
    "fr": (
        "{product} à {price} € au lieu de {ref} €",
        "{product} en promotion chez Coolblue : {price} € au lieu de {ref} €, soit "
        "-{pct} %. Prix relevé le 7 novembre 2026 sur coolblue.be. Livraison gratuite en "
        "Belgique ; vérifiez la disponibilité avant d'acheter.",
    ),
    "nl": (
        "{product} voor {price} € in plaats van {ref} €",
        "{product} in promotie bij Coolblue: {price} € in plaats van {ref} €, of -{pct} %. "
        "Prijs vastgesteld op 7 november 2026 op coolblue.be. Gratis levering in België; "
        "controleer de beschikbaarheid voor je koopt.",
    ),
    "de": (
        "{product} für {price} € statt {ref} €",
        "{product} im Angebot bei Coolblue: {price} € statt {ref} €, also -{pct} %. Preis "
        "festgestellt am 7. November 2026 auf coolblue.be. Kostenlose Lieferung in Belgien; "
        "vor dem Kauf die Verfügbarkeit prüfen.",
    ),
}


def _money(value):
    """Decimal('1099.00') → « 1 099 » ; Decimal('20.99') → « 20,99 » (format belge)."""
    whole, cents = f"{value:.2f}".split(".")
    whole = f"{int(whole):,}".replace(",", " ")
    return whole if cents == "00" else f"{whole},{cents}"


def coolblue_deals(*, categories, members_pool, moderator):
    """Crée les offres relevées sur Coolblue, leurs traductions, photos et décisions."""
    coolblue = Merchant.objects.get(slug="coolblue")
    items = json.loads((DATA / "coolblue.json").read_text(encoding="utf-8"))
    now = timezone.now()
    # Une offre déjà présente dans la sélection rédigée à la main (DEALS de
    # seed_demo) garde son texte soigné : on ne l'écrase pas par le gabarit.
    curated = set(
        Deal.objects.exclude(slug__regex=r"-cb\d+$").values_list("external_url", flat=True)
    )
    created = []
    for index, item in enumerate(items):
        if item["url"] in curated:
            continue
        price, ref = Decimal(item["price"]), Decimal(item["reference"])
        pct = int(round((1 - price / ref) * 100))
        product = item["title"][:95]
        texts = {
            lang: (
                title.format(product=product, price=_money(price), ref=_money(ref)),
                body.format(product=product, price=_money(price), ref=_money(ref), pct=pct),
            )
            for lang, (title, body) in TEMPLATES.items()
        }
        pending = index % 15 == 14  # quelques offres restent en file de modération
        published = None if pending else now - timedelta(hours=random.randint(1, 300))
        deal, _ = Deal.objects.update_or_create(
            external_url=item["url"],
            defaults={
                "title": texts["fr"][0][:140],
                "slug": f"{slugify(product)[:130]}-cb{index}",
                "description": texts["fr"][1],
                "price": price,
                "reference_price": ref,
                "shipping_cost": Decimal("0.00"),
                "merchant": coolblue,
                "category": categories["high-tech" if item["kind"] in HIGH_TECH else "maison"],
                "submitted_by": members_pool[index % len(members_pool)],
                "status": DealStatus.PENDING if pending else DealStatus.PUBLISHED,
                "language": "fr",
                "image_url": item["image"],
                "temperature": random.randint(80, 950),
                "published_at": published,
                "starts_at": published or now,
            },
        )
        for lang in ("nl", "de"):
            DealTranslation.objects.update_or_create(
                deal=deal,
                language=lang,
                defaults={
                    "title": texts[lang][0][:140],
                    "description": texts[lang][1],
                    # Traduction produite par un gabarit relu, à partir des champs
                    # chiffrés de l'offre : pas un moteur de traduction automatique.
                    "is_machine_translated": False,
                },
            )
        for position, url in enumerate(item["gallery"], start=1):
            DealImage.objects.update_or_create(
                deal=deal, position=position, defaults={"image_url": url}
            )
        if not pending:
            ModerationDecision.objects.get_or_create(
                deal=deal,
                moderator=moderator,
                defaults={
                    "decision": ModerationDecision.Decision.APPROVED,
                    "reason": "Prix et prix de référence contrôlés sur coolblue.be.",
                },
            )
        created.append(deal)
    return created


# -- Commentaires multilingues ---------------------------------------------------
OPENERS = [
    ("Commandé hier,", "Gisteren besteld,", "Gestern bestellt,"),
    ("Acheté ce matin,", "Vanmorgen gekocht,", "Heute Morgen gekauft,"),
    (
        "Je l'ai depuis une semaine :",
        "Ik heb het sinds een week:",
        "Ich habe es seit einer Woche:",
    ),
    ("Bon plan,", "Goede deal,", "Gutes Angebot,"),
    (
        "Vu en magasin à Liège,",
        "Gezien in de winkel in Luik,",
        "Im Geschäft in Lüttich gesehen,",
    ),
    ("Après comparaison,", "Na vergelijking:", "Nach einem Vergleich:"),
    ("Merci pour le partage,", "Bedankt om te delen,", "Danke fürs Teilen,"),
    ("Attention,", "Let op,", "Achtung,"),
    (
        "Retrait à Gand sans souci,",
        "Zonder problemen afgehaald in Gent,",
        "Problemlos in Gent abgeholt,",
    ),
    ("Testé ce week-end,", "Dit weekend getest,", "Am Wochenende getestet,"),
    ("Commande passée ce midi,", "Vanmiddag besteld,", "Heute Mittag bestellt,"),
    ("Pour info,", "Ter info:", "Zur Info:"),
]
DETAILS = [
    (
        "livré le lendemain comme annoncé.",
        "de volgende dag geleverd zoals aangekondigd.",
        "am nächsten Tag wie angekündigt geliefert.",
    ),
    (
        "le prix du panier correspond bien à l'annonce.",
        "de prijs in het winkelmandje klopt met de aanbieding.",
        "der Preis im Warenkorb stimmt mit dem Angebot überein.",
    ),
    ("la qualité est au rendez-vous.", "de kwaliteit is uitstekend.", "die Qualität stimmt."),
    (
        "c'est le meilleur prix que j'ai trouvé en Belgique.",
        "het is de beste prijs die ik in België vond.",
        "das ist der beste Preis, den ich in Belgien gefunden habe.",
    ),
    (
        "vérifiez le prix des 30 derniers jours avant d'acheter.",
        "controleer de prijs van de voorbije 30 dagen voor je koopt.",
        "prüft vor dem Kauf den Preis der letzten 30 Tage.",
    ),
    ("le stock baisse vite.", "de voorraad slinkt snel.", "der Vorrat geht schnell zur Neige."),
    (
        "emballage soigné, rien à redire.",
        "zorgvuldig verpakt, niets op aan te merken.",
        "sorgfältig verpackt, nichts auszusetzen.",
    ),
    (
        "le service client a répondu en une heure.",
        "de klantendienst antwoordde binnen het uur.",
        "der Kundendienst hat innerhalb einer Stunde geantwortet.",
    ),
    (
        "un peu bruyant mais très efficace.",
        "wat luidruchtig maar zeer efficiënt.",
        "etwas laut, aber sehr effizient.",
    ),
    (
        "parfait pour un petit appartement.",
        "perfect voor een klein appartement.",
        "perfekt für eine kleine Wohnung.",
    ),
    (
        "la garantie est de deux ans chez ce marchand.",
        "bij deze handelaar geldt twee jaar garantie.",
        "bei diesem Händler gibt es zwei Jahre Garantie.",
    ),
    (
        "je recommande sans hésiter.",
        "ik raad het zonder aarzelen aan.",
        "ich kann es ohne Zögern empfehlen.",
    ),
]


def comments(deals, members_pool):
    """Un à trois commentaires par offre publiée, chacun traduit dans les deux autres langues."""
    count = 0
    for deal in deals:
        if deal.status != DealStatus.PUBLISHED:
            continue
        for _ in range(random.randint(1, 3)):
            opener, detail = random.choice(OPENERS), random.choice(DETAILS)
            texts = {
                lang: f"{opener[i]} {detail[i]}" for i, lang in enumerate(("fr", "nl", "de"))
            }
            author = random.choice(members_pool)
            if author == deal.submitted_by:
                continue
            source = author.preferred_language if author.preferred_language in texts else "fr"
            comment, created = Comment.objects.get_or_create(
                deal=deal,
                author=author,
                body=texts[source],
                defaults={"language": source, "is_verified_purchase": random.random() < 0.35},
            )
            count += created
            for lang, text in texts.items():
                if lang != source:
                    CommentTranslation.objects.update_or_create(
                        comment=comment, language=lang, defaults={"body": text}
                    )
    return count


# -- Alertes ------------------------------------------------------------------------
ALERT_KEYWORDS = [
    ("tv", "high-tech", 600),
    ("iphone", "high-tech", 900),
    ("dyson", "maison", 450),
    ("lave-linge", "maison", 650),
    ("airfryer", "maison", 150),
    ("nespresso", "maison", 120),
    ("samsung", "high-tech", None),
    ("pc portable", "high-tech", 800),
    ("tablette", "high-tech", 300),
    ("robot aspirateur", "maison", 500),
    ("lego", None, 80),
    ("montre connectée", "high-tech", 300),
    ("barre de son", "high-tech", 400),
    ("switch 2", "high-tech", 470),
    ("café en grains", "supermarche", 25),
    ("frigo", "maison", 900),
    ("lave-vaisselle", "maison", 600),
    ("casque", "high-tech", 250),
    ("fibre", "telecom", 50),
    ("chaussures", "mode", 120),
]


def alerts(members_pool, categories):
    count = 0
    for user in members_pool:
        for keyword, category, max_price in random.sample(
            ALERT_KEYWORDS, k=random.randint(1, 2)
        ):
            _, created = Alert.objects.get_or_create(
                user=user,
                keyword=keyword,
                defaults={
                    "category": categories.get(category) if category else None,
                    "max_price": Decimal(max_price) if max_price else None,
                    "is_active": random.random() < 0.85,
                },
            )
            count += created
    return count


# -- Paiements et abonnements -------------------------------------------------------
def payments(members_pool):
    plans = list(Plan.objects.filter(code__in=["vip-annuel", "vip-mensuel"]))
    brands = ["visa", "mastercard", "bancontact"]
    count = 0
    for index, user in enumerate(members_pool):
        reference = f"sbx_seed_{user.pk.hex[:16]}"
        if Payment.objects.filter(gateway_reference=reference).exists():
            continue
        plan = plans[index % len(plans)]
        failed = index % 12 == 11  # un paiement sur douze refusé par la banque
        settled = timezone.now() - timedelta(days=random.randint(1, 330))
        payment = Payment.objects.create(
            reference=Payment.next_reference(),
            user=user,
            plan=plan,
            amount=plan.price,
            vat_amount=(plan.price * plan.vat_rate / (100 + plan.vat_rate)).quantize(
                Decimal("0.01")
            ),
            status=Payment.Status.FAILED if failed else Payment.Status.SUCCEEDED,
            gateway="sandbox",
            gateway_reference=reference,
            card_brand=brands[index % 3],
            card_last4=f"{random.randint(0, 9999):04d}",
            settled_at=None if failed else settled,
        )
        if not failed:
            ends = settled + timedelta(days=plan.duration_days)
            Subscription.objects.create(
                user=user,
                plan=plan,
                payment=payment,
                started_at=settled,
                ends_at=ends,
                status="active" if ends > timezone.now() else "expired",
            )
        count += 1
    return count


# -- Signalements -------------------------------------------------------------------
REPORT_DETAILS = {
    Report.Reason.OUT_OF_STOCK: [
        "Plus disponible en ligne depuis ce matin.",
        "Rupture de stock dans les magasins de Bruxelles.",
        "Le coloris annoncé n'est plus proposé.",
    ],
    Report.Reason.WRONG_PRICE: [
        "Le prix affiché au panier est plus élevé que l'annonce.",
        "Le prix a augmenté de 20 € depuis la publication.",
        "Le prix ne vaut que pour la version reconditionnée.",
    ],
    Report.Reason.MISLEADING: [
        "Le prix barré ne correspond pas au plus bas des 30 derniers jours.",
        "La réduction annoncée inclut un cashback soumis à conditions.",
    ],
    Report.Reason.AFFILIATE: ["Le lien contient un identifiant d'affiliation personnel."],
    Report.Reason.SPAM: ["Compte qui publie uniquement les offres d'une même enseigne."],
}


def reports(deals, members_pool, moderator):
    published = [d for d in deals if d.status == DealStatus.PUBLISHED]
    count, attempts = 0, 0
    while count < 110 and attempts < 1000:
        attempts += 1
        deal, reporter = random.choice(published), random.choice(members_pool)
        reason = random.choice(list(REPORT_DETAILS))
        status = random.choices(["open", "resolved", "dismissed"], weights=[50, 30, 20])[0]
        _, created = Report.objects.get_or_create(
            deal=deal,
            reporter=reporter,
            defaults={
                "reason": reason,
                "detail": random.choice(REPORT_DETAILS[reason]),
                "status": status,
                "resolved_at": None if status == "open" else timezone.now(),
                "resolved_by": None if status == "open" else moderator,
            },
        )
        count += created
    return count


# -- Piste d'audit --------------------------------------------------------------------
def audit_trail(users, deals):
    """Rejoue les événements du jeu de données dans le journal d'audit (une seule fois)."""
    if AuditLog.objects.filter(metadata__seed=True).exists():
        return 0
    user_type = ContentType.objects.get_for_model(User)
    deal_type = ContentType.objects.get_for_model(Deal)
    payment_type = ContentType.objects.get_for_model(Payment)
    entries = []

    def add(action, actor, target_type, target_id, **meta):
        entries.append(
            AuditLog(
                action=action,
                actor=actor,
                actor_label=str(actor) if actor else "",
                target_type=target_type,
                target_id=str(target_id),
                ip_address=f"192.0.2.{random.randint(1, 254)}",  # plage réservée (RFC 5737)
                method="POST",
                metadata={"seed": True, **meta},
            )
        )

    for user in users:
        add(AuditLog.Action.USER_REGISTERED, user, user_type, user.pk)
        add(AuditLog.Action.USER_LOGIN, user, user_type, user.pk)
    for deal in deals:
        add(AuditLog.Action.DEAL_SUBMITTED, deal.submitted_by, deal_type, deal.pk)
        if deal.status == DealStatus.PUBLISHED:
            add(AuditLog.Action.DEAL_PUBLISHED, None, deal_type, deal.pk, by="moderation")
    for payment in Payment.objects.filter(gateway_reference__startswith="sbx_seed_"):
        action = (
            AuditLog.Action.PAYMENT_SUCCEEDED
            if payment.status == Payment.Status.SUCCEEDED
            else AuditLog.Action.PAYMENT_FAILED
        )
        add(action, payment.user, payment_type, payment.pk, reference=payment.reference)
    AuditLog.objects.bulk_create(entries)
    return len(entries)


# -- Alertes déclenchées (VIP en priorité) ---------------------------------------------
def alert_matches(deals):
    """
    Rejoue la distribution des alertes pour les offres publiées : le VIP reçoit
    l'alerte à la publication, les autres membres ALERT_DELAY plus tard.
    """
    from apps.deals.models import AlertMatch
    from apps.deals.vip import ALERT_DELAY
    from apps.deals.vip import alert_matches as find

    alerts = list(Alert.objects.filter(is_active=True).select_related("user"))
    now, count = timezone.now(), 0
    for deal in deals:
        if deal.status != DealStatus.PUBLISHED or not deal.published_at:
            continue
        for alert in find(deal, alerts):
            if alert.user_id == deal.submitted_by_id:
                continue
            vip = alert.user.is_vip
            available = deal.published_at if vip else deal.published_at + ALERT_DELAY
            _, created = AlertMatch.objects.get_or_create(
                alert=alert,
                deal=deal,
                defaults={
                    "available_at": available,
                    "is_priority": vip,
                    "notified_at": available if available <= now else None,
                },
            )
            count += created
    return count
