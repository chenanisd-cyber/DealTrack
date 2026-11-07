"""
Importe des commerçants indépendants depuis OpenStreetMap.

    python manage.py import_local_merchants --area "Gent"
    python manage.py import_local_merchants --area "Bruxelles - Brussel" --admin-level 8

Pourquoi OpenStreetMap et pas Google Maps ? Google Places exige une clé
d'API facturée et ses conditions interdisent de recopier les fiches dans une
autre base. OpenStreetMap est une base ouverte (licence ODbL) : la
réutilisation est autorisée à condition de citer « © les contributeurs
OpenStreetMap », ce que fait la page des commerçants locaux.

Filtre « indépendant » : on écarte les fiches portant une marque (tags
`brand` / `brand:wikidata`), signe d'une chaîne. Le filtre n'est pas parfait :
chaque commerçant importé arrive donc NON vérifié, la modération confirme.
"""

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import SHOP_TYPES, Merchant

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "DealTrack.be (projet etudiant; import commercants locaux)"}

# Couleur de vignette par type de commerce (quand le commerçant n'a ni photo ni logo).
SHOP_COLORS = {
    "bakery": "#A0522D",
    "pastry": "#C2185B",
    "butcher": "#8E1B1B",
    "cheese": "#E0A800",
    "deli": "#5D4037",
    "greengrocer": "#2E7D32",
    "wine": "#6A1B4D",
    "coffee": "#4E342E",
    "chocolate": "#3E2723",
    "books": "#1A4D7A",
    "bicycle": "#00796B",
}


def build_query(area, admin_level, limit):
    shop_types = "|".join(SHOP_TYPES)
    level = (
        f'["admin_level"="{admin_level}"]' if admin_level else '["boundary"="administrative"]'
    )
    return (
        "[out:json][timeout:40];"
        f'area["name"="{area}"]{level}->.a;'
        f'(nwr["shop"~"^({shop_types})$"]["name"][!"brand"][!"brand:wikidata"](area.a););'
        f"out center tags {int(limit)};"
    )


def merchant_from_element(element, default_city):
    """Traduit un élément OSM en champs de Merchant (None si inexploitable)."""
    tags = element.get("tags", {})
    name = (tags.get("name") or "").strip()
    shop = tags.get("shop", "")
    if not name or shop not in SHOP_TYPES:
        return None
    lat = element.get("lat") or element.get("center", {}).get("lat")
    lon = element.get("lon") or element.get("center", {}).get("lon")
    street = " ".join(filter(None, [tags.get("addr:street"), tags.get("addr:housenumber")]))
    postcode_city = " ".join(filter(None, [tags.get("addr:postcode"), tags.get("addr:city")]))
    website = (tags.get("website") or tags.get("contact:website") or "").strip()
    if website and not website.startswith(("http://", "https://")):
        website = "https://" + website
    return {
        "name": name[:120],
        "shop_type": shop,
        "address": ", ".join(filter(None, [street, postcode_city]))[:200],
        "city": (tags.get("addr:city") or default_city)[:80],
        "latitude": round(lat, 6) if lat is not None else None,
        "longitude": round(lon, 6) if lon is not None else None,
        "website": website[:300] if website.startswith("https://") else "",
    }


class Command(BaseCommand):
    help = "Importe des commerçants indépendants depuis OpenStreetMap (Overpass API)."

    def add_arguments(self, parser):
        parser.add_argument("--area", required=True, help='Nom OSM de la zone, ex. "Gent".')
        parser.add_argument(
            "--admin-level", default="", help="Niveau administratif OSM (8 = commune)."
        )
        parser.add_argument(
            "--city", default="", help="Ville affichée si l'adresse n'en donne pas."
        )
        parser.add_argument("--limit", type=int, default=25)
        parser.add_argument("--dry-run", action="store_true", help="Affiche sans enregistrer.")

    def handle(self, *args, area, admin_level, city, limit, dry_run, **options):
        query = build_query(area, admin_level, limit)
        try:
            response = requests.post(
                OVERPASS_URL, data={"data": query}, headers=HEADERS, timeout=60
            )
            response.raise_for_status()
            elements = response.json().get("elements", [])
        except (requests.RequestException, ValueError) as exc:
            raise CommandError(f"OpenStreetMap injoignable : {exc}") from exc

        created = updated = 0
        with transaction.atomic():
            for element in elements:
                fields = merchant_from_element(element, city or area.split(" - ")[0])
                if fields is None:
                    continue
                if dry_run:
                    self.stdout.write(
                        f"  {fields['name']} ({fields['shop_type']}) {fields['address']}"
                    )
                    continue
                _, was_created = Merchant.objects.update_or_create(
                    osm_id=element["id"],
                    defaults={
                        **fields,
                        "country": "BE",
                        "is_local_independent": True,
                        "brand_color": SHOP_COLORS.get(fields["shop_type"], "#01182B"),
                    },
                    create_defaults={
                        **fields,
                        "country": "BE",
                        "is_local_independent": True,
                        "is_verified": False,
                        "brand_color": SHOP_COLORS.get(fields["shop_type"], "#01182B"),
                        "slug": unique_slug(fields["name"], element["id"]),
                    },
                )
                created += was_created
                updated += not was_created

        self.stdout.write(
            self.style.SUCCESS(
                f"{created} commerçant(s) ajouté(s), {updated} mis à jour "
                "— données © les contributeurs OpenStreetMap (ODbL)."
            )
        )


def unique_slug(name, osm_id):
    base = slugify(name)[:100] or "commerce"
    slug = base
    if Merchant.objects.filter(slug=slug).exists():
        slug = f"{base}-{osm_id}"
    return slug
