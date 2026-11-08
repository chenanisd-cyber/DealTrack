"""
Avantages de l'abonnement VIP.

1. Historique du prix : chaque offre garde un journal de prix (PricePoint).
   Un point est ajouté à la création, à chaque changement de prix (édition,
   modération) et par la commande « track_prices » qui relit les pages
   lisibles. Le graphique n'affiche que des prix réellement observés.
2. Comparaison : la même offre chez d'autres marchands de DealTrack, une
   recherche en direct sur Amazon.com.be et des liens de recherche vers les
   grandes enseignes belges.
3. Alertes en priorité : à la publication d'une offre, les alertes qui
   correspondent sont libérées tout de suite pour les VIP, et après
   ALERT_DELAY pour les autres membres.
"""

import hashlib
import logging
import re
import unicodedata
from datetime import timedelta
from decimal import Decimal
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

ALERT_DELAY = timedelta(hours=getattr(settings, "ALERT_DELAY_HOURS", 2))


# -- Outils texte -----------------------------------------------------------------
def normalize(text):
    """Minuscules, sans accents ni ponctuation : « Téléviseur 55\" » → « televiseur 55 »."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


STOP_WORDS = {
    "a",
    "au",
    "aux",
    "avec",
    "de",
    "des",
    "du",
    "en",
    "et",
    "la",
    "le",
    "les",
    "lieu",
    "pour",
    "sur",
    "un",
    "une",
    "voor",
    "van",
    "met",
    "het",
    "een",
    "plaats",
    "fur",
    "statt",
    "mit",
    "und",
    "der",
    "die",
    "das",
    "eur",
    "noir",
    "blanc",
    "gris",
    "go",
    "gb",
}


def product_name(title):
    """« TV Philips 43\" à 349 € au lieu de 449 € » → « TV Philips 43\" » (partie produit)."""
    return re.split(r"\s+(?:à|voor|für|a)\s+\d|\s+au lieu de\s+", title or "", maxsplit=1)[
        0
    ].strip()


def tokens(text):
    return {
        t for t in normalize(product_name(text)).split() if t not in STOP_WORDS and len(t) > 1
    }


# -- 1. Historique du prix ---------------------------------------------------------
def record_price(deal, *, source=None, at=None):
    """Ajoute un point si le prix a changé depuis le dernier relevé (ou s'il n'y en a aucun)."""
    from .models import PricePoint

    last = deal.price_history.order_by("-recorded_at", "-id").first()
    if last is not None and last.price == deal.price:
        return None
    return PricePoint.objects.create(
        deal=deal,
        price=deal.price,
        source=source
        or (PricePoint.Source.SURVEY if last is None else PricePoint.Source.UPDATE),
        recorded_at=at or timezone.now(),
    )


def price_chart(deal, width=560, height=180, pad=28):
    """
    Données du graphique SVG (calculé côté serveur : aucune bibliothèque JS).
    Renvoie None s'il n'y a aucun point.
    """
    points = list(deal.price_history.order_by("recorded_at", "id"))
    if not points:
        return None
    prices = [p.price for p in points]
    reference = deal.reference_price
    low = min(prices + ([reference] if reference else []))
    high = max(prices + ([reference] if reference else []))
    span = (high - low) or Decimal("1")
    start, end = points[0].recorded_at, points[-1].recorded_at
    duration = (end - start).total_seconds() or 1

    def x(point):
        if len(points) == 1:
            return width / 2
        return pad + (width - 2 * pad) * (point.recorded_at - start).total_seconds() / duration

    def y(price):
        return height - pad - float((price - low) / span) * (height - 2 * pad)

    coords = [(round(x(p), 1), round(y(p.price), 1), p) for p in points]
    return {
        "width": width,
        "height": height,
        "polyline": " ".join(f"{cx},{cy}" for cx, cy, _ in coords),
        "dots": [
            {
                "x": cx,
                "y": cy,
                "price": p.price,
                "date": p.recorded_at,
                "source": p.get_source_display(),
            }
            for cx, cy, p in coords
        ],
        "reference_y": round(y(reference), 1) if reference else None,
        "reference": reference,
        "lowest": min(prices),
        "highest": max(prices),
        "since": start,
        "count": len(points),
    }


# -- 2. Comparaison ---------------------------------------------------------------
def similar_deals(deal, limit=5):
    """La même offre chez d'autres marchands de DealTrack (titres proches, mêmes références)."""
    from .models import Deal

    wanted = tokens(deal.title)
    if not wanted:
        return []
    models_refs = {t for t in wanted if any(c.isdigit() for c in t) and len(t) >= 3}
    candidates = Deal.objects.live().exclude(pk=deal.pk).select_related("merchant")
    if models_refs:
        query = None
        from django.db.models import Q

        for ref in models_refs:
            clause = Q(title__icontains=ref)
            query = clause if query is None else query | clause
        candidates = candidates.filter(query)
    scored = []
    for other in candidates[:200]:
        theirs = tokens(other.title)
        if not theirs:
            continue
        score = len(wanted & theirs) / len(wanted | theirs)
        if score >= 0.5 or (models_refs and models_refs <= theirs):
            scored.append((score, other))
    scored.sort(key=lambda item: (-item[0], item[1].price))
    return [other for _, other in scored[:limit]]


SEARCH_SITES = [
    ("Coolblue", "https://www.coolblue.be/fr/rechercher?query={q}"),
    ("bol.com", "https://www.bol.com/be/fr/s/?searchtext={q}"),
    ("MediaMarkt", "https://www.mediamarkt.be/fr/search.html?query={q}"),
    ("Krëfel", "https://www.krefel.be/fr/search?text={q}"),
    ("Amazon.com.be", "https://www.amazon.com.be/s?k={q}&language=fr_BE"),
]


def search_links(deal):
    query = quote_plus(product_name(deal.title)[:80])
    return [{"site": site, "url": url.format(q=query)} for site, url in SEARCH_SITES]


def amazon_offers(deal, limit=3):
    """
    Recherche en direct sur Amazon.com.be (mise en cache 12 h, 10 min si vide). Passe par le
    téléchargeur protégé contre la SSRF du scraper. En cas de blocage, liste vide.
    """
    from .scraper import BlockedError, UnsafeURLError, _download, parse_price

    query = product_name(deal.title)[:80]
    digest = hashlib.sha256(normalize(query).encode()).hexdigest()
    key = f"amazon-offers:{digest}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    url = f"https://www.amazon.com.be/s?k={quote_plus(query)}&language=fr_BE"
    offers = []
    try:
        final_url, content = _download(url)
        soup = BeautifulSoup(content, "html.parser")
        for result in soup.select('div[data-component-type="s-search-result"]'):
            if "Sponsoris" in result.get_text(" "):
                continue
            title = result.select_one("h2")
            price = result.select_one(".a-price:not(.a-text-price) .a-offscreen")
            link = result.select_one('a[href*="/dp/"]')
            if not (title and price and link):
                continue
            offers.append(
                {
                    "title": " ".join(title.get_text(" ").split())[:140],
                    "price": str(parse_price(price.get_text()) or ""),
                    "url": urljoin(final_url, link["href"]).split("?")[0],
                }
            )
            if len(offers) == limit:
                break
    except (BlockedError, UnsafeURLError, OSError, Exception) as exc:  # noqa: BLE001
        logger.info(
            "Comparaison Amazon indisponible (%s) pour %s", exc.__class__.__name__, query
        )
    # Un résultat vide (page de vérification, panne) n'est gardé que 10 minutes.
    cache.set(key, offers, 60 * 60 * 12 if offers else 60 * 10)
    return offers


# -- 3. Alertes en priorité ----------------------------------------------------------
def alert_matches(deal, alerts):
    """Alertes (actives) dont le mot-clé, la catégorie et le prix maximum correspondent."""
    title = normalize(deal.title)
    found = []
    for alert in alerts:
        words = normalize(alert.keyword).split()
        if not words or not all(re.search(rf"\b{re.escape(w)}", title) for w in words):
            continue
        if alert.category_id and alert.category_id != deal.category_id:
            continue
        if alert.max_price is not None and deal.price > alert.max_price:
            continue
        found.append(alert)
    return found


def dispatch_alerts(deal, *, at=None):
    """
    Crée les correspondances d'alertes d'une offre publiée. Le VIP reçoit
    l'alerte tout de suite ; les autres membres après ALERT_DELAY.
    """
    from .models import Alert, AlertMatch, Deal

    at = at or timezone.now()
    alerts = Alert.objects.filter(is_active=True).select_related("user")
    created = 0
    for alert in alert_matches(deal, alerts):
        if alert.user_id == deal.submitted_by_id:
            continue
        vip = alert.user.is_vip
        _, was_created = AlertMatch.objects.get_or_create(
            alert=alert,
            deal=deal,
            defaults={"available_at": at if vip else at + ALERT_DELAY, "is_priority": vip},
        )
        created += was_created
    Deal.objects.filter(pk=deal.pk).update(alerts_dispatched_at=at)
    deal.alerts_dispatched_at = at
    return created
