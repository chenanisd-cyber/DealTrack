"""
Marchand d'une offre déduit de son lien.

Le membre n'a plus à choisir dans une liste : un lien joybuy.nl donne le
marchand « Joybuy », créé à la volée s'il n'existe pas encore. Il arrive
alors « non vérifié » : la modération confirme l'enseigne avant de lui
donner le badge « Offre vérifiée ».
"""

import hashlib
from urllib.parse import urlparse

from django.utils.text import slugify

from .models import Merchant

# Pays déduit du domaine de premier niveau ; .com, .eu… restent « autre pays ».
TLD_COUNTRIES = {"be": "BE", "nl": "NL", "fr": "FR", "de": "DE", "lu": "LU"}

# Couleurs de vignette attribuées aux nouveaux marchands (choix stable par nom).
PALETTE = ["#1A4D7A", "#00796B", "#6A1B4D", "#8E1B1B", "#5D4037", "#2E7D32", "#C2185B"]


def domain_of(url):
    """« https://www.joybuy.nl/x » → « joybuy.nl » (chaîne vide si invalide)."""
    host = (urlparse(url or "").hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def find_merchant(url):
    """Marchand existant dont le site correspond au domaine (sous-domaines compris)."""
    host = domain_of(url)
    if not host:
        return None
    for merchant in Merchant.objects.exclude(website=""):
        domain = domain_of(merchant.website)
        if domain and (host == domain or host.endswith("." + domain)):
            return merchant
    return None


def name_from_domain(domain):
    """« joybuy.nl » → « Joybuy » ; « amazon.com.be » → « Amazon »."""
    label = domain.split(".")[0] if domain else ""
    return label.replace("-", " ").title()


def build_merchant(*, url="", name=""):
    """
    Renvoie le marchand correspondant au lien, ou un NOUVEAU marchand non
    enregistré (l'appelant le sauvegarde avec l'offre). Sans lien, le nom
    saisi par le membre sert de clé (insensible à la casse).
    """
    existing = find_merchant(url)
    if existing:
        return existing

    domain = domain_of(url)
    name = (name or name_from_domain(domain)).strip()[:120]
    if not name:
        return None
    by_name = Merchant.objects.filter(name__iexact=name).first()
    if by_name:
        return by_name

    tld = domain.rsplit(".", 1)[-1] if domain else ""
    color = PALETTE[int(hashlib.sha256(name.encode()).hexdigest(), 16) % len(PALETTE)]
    return Merchant(
        name=name,
        slug=_unique_slug(name),
        country=TLD_COUNTRIES.get(tld, "BE" if not domain else Merchant.Country.OTHER),
        website=f"https://{urlparse(url).hostname}" if domain else "",
        is_verified=False,
        brand_color=color,
    )


def _unique_slug(name):
    base = slugify(name)[:100] or "marchand"
    slug, n = base, 1
    while Merchant.objects.filter(slug=slug).exists():
        n += 1
        slug = f"{base}-{n}"
    return slug
