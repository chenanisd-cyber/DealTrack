"""
Pré-remplissage du formulaire de dépôt à partir du lien d'une offre.

Le serveur va chercher une page dont l'adresse est fournie par l'utilisateur :
c'est le scénario type d'une faille SSRF (Server-Side Request Forgery, OWASP
A10). Sans contrôle, un visiteur pourrait faire interroger par le serveur
http://127.0.0.1, le réseau interne ou l'adresse de métadonnées d'un
hébergeur cloud (169.254.169.254). Les protections appliquées ici :

1. seuls les schémas http et https sont acceptés ;
2. le nom de domaine est résolu et TOUTES ses adresses IP doivent être
   publiques (ni privées, ni locales, ni réservées) ;
3. les redirections sont suivies à la main, et chaque étape est revérifiée :
   sinon une page publique pourrait rediriger vers 127.0.0.1 ;
4. la réponse est lue par morceaux et coupée au-delà de MAX_BYTES (3 Mo) ;
5. les messages renvoyés au client restent génériques, le détail technique
   part dans les logs.
"""

import ipaddress
import json
import logging
import re
import socket
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = {"http", "https"}
MAX_BYTES = 3_000_000  # 3 Mo : certaines fiches produit (Amazon) dépassent 1 Mo
MAX_REDIRECTS = 3
TIMEOUT = 5  # secondes
HEADERS = {"User-Agent": "DealTrackBot/1.0 (+https://dealtrack.be)"}


class UnsafeURLError(ValueError):
    """Adresse refusée : schéma interdit ou destination non publique."""


def validate_public_url(url):
    """
    Lève UnsafeURLError si l'URL ne pointe pas vers une machine publique.

    Limite connue : entre cette vérification et la connexion, un DNS
    malveillant pourrait changer de réponse (« DNS rebinding »). Le risque
    reste faible ici : la requête est en lecture seule et la réponse n'est
    jamais renvoyée telle quelle au client.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES or not parsed.hostname:
        raise UnsafeURLError("schéma ou hôte invalide")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(parsed.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeURLError("nom de domaine introuvable") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise UnsafeURLError(f"adresse non publique : {ip}")


def _download(url):
    """Télécharge la page en suivant les redirections, chacune revérifiée."""
    for _ in range(MAX_REDIRECTS + 1):
        validate_public_url(url)
        response = requests.get(
            url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=False, stream=True
        )
        if response.is_redirect:
            url = urljoin(url, response.headers.get("Location", ""))
            response.close()
            continue

        if response.status_code in (401, 403, 429, 503):
            response.close()
            raise BlockedError(response.status_code)
        response.raise_for_status()
        content = b""
        for chunk in response.iter_content(chunk_size=16_384):
            content += chunk
            if len(content) > MAX_BYTES:
                break
        response.close()
        return url, content[:MAX_BYTES]

    raise UnsafeURLError("trop de redirections")


class BlockedError(Exception):
    """Le site refuse la lecture automatique (403, 429, 503…)."""


def fetch_deal_info(url):
    """
    Lit la page d'une offre et en extrait ce qui pré-remplit le formulaire :
    titre, photo, prix, prix de référence légal, description.

    Sources, de la plus fiable à la moins fiable :
      1. les données structurées JSON-LD (schema.org/Product) que les boutiques
         publient pour Google ;
      2. les balises meta (Open Graph, product:price:amount, itemprop) ;
      3. quelques repères propres à Amazon, très utilisé en Belgique.
    Un site qui bloque les robots n'est pas contourné : le membre complète
    alors le formulaire lui-même.
    """
    try:
        final_url, content = _download(url)
    except UnsafeURLError as exc:
        logger.warning("Lien refusé (%s) : %s", exc, url)
        return {"success": False, "error": "unsafe_url"}
    except BlockedError:
        logger.info("Lecture automatique refusée par le site : %s", url)
        return {"success": False, "error": "blocked"}
    except requests.RequestException as exc:
        logger.info("Lien injoignable (%s) : %s", exc.__class__.__name__, url)
        return {"success": False, "error": "unreachable"}

    soup = BeautifulSoup(content, "html.parser")
    product = next(_json_ld_products(soup), {})
    offer = _first_offer(product)

    title = (
        _text(product.get("name"))
        or _meta(soup, "og:title")
        or _select_text(soup, "#productTitle")
        or (soup.title.get_text(strip=True) if soup.title else "")
    )
    title = re.sub(r"^Amazon\.[a-z.]+\s*:\s*", "", title).split(" | ")[0].strip()

    image_url = ""
    for candidate in (
        _first_image(product.get("image")),
        _meta(soup, "og:image"),
        _attr(soup, "#landingImage", "data-old-hires"),
    ):
        if candidate:
            candidate = urljoin(final_url, candidate.strip())
            # https uniquement : écarte data:, javascript: et le contenu mixte http.
            if urlparse(candidate).scheme == "https":
                image_url = candidate
                break

    price = (
        parse_price(offer.get("price") or offer.get("lowPrice"))
        or parse_price(_meta(soup, "product:price:amount"))
        or parse_price(_meta(soup, "og:price:amount"))
        or parse_price(_attr(soup, '[itemprop="price"]', "content"))
        or parse_price(_select_text(soup, ".priceToPay .a-offscreen"))
        or parse_price(_select_text(soup, "#corePrice_feature_div .a-offscreen"))
    )

    # Prix de référence : uniquement le « prix le plus bas des 30 derniers
    # jours » (art. VI.18 CDE). Un prix « conseillé » ou barré sans cette
    # mention n'est pas repris : c'est au membre de le vérifier.
    reference = None
    match = LOWEST_30_DAYS.search(soup.get_text(" ", strip=True))
    if match:
        reference = parse_price(match.group(1))
    if reference is not None and price is not None and reference <= price:
        reference = None

    description = (
        _text(product.get("description"))
        or _meta(soup, "og:description")
        or _meta(soup, "description", attr="name")
    )

    return {
        "success": True,
        "title": title[:140],  # max_length du champ Deal.title
        "url": url,
        "final_url": final_url,
        "image_url": image_url[:800],
        "price": str(price) if price is not None else "",
        "reference_price": str(reference) if reference is not None else "",
        "description": " ".join(description.split())[:1500],
        "site_name": _meta(soup, "og:site_name")[:120],
    }


# -- Extraction --------------------------------------------------------------
LOWEST_30_DAYS = re.compile(
    r"(?:prix le plus bas des 30 derniers jours|laagste prijs (?:van|in) de "
    r"(?:afgelopen|laatste) 30 dagen|niedrigster preis der letzten 30 tage)"
    r"\s*:?\s*(?:€\s*)?([\d.,]+)",
    re.IGNORECASE,
)


def parse_price(value):
    """
    Convertit « 1.229,00 € », « € 399,- », « 502,60€ » ou « 399.00 » en
    Decimal. Renvoie None si la valeur n'est pas un prix plausible.
    """
    if value is None:
        return None
    text = str(value).replace("\xa0", " ")
    match = re.search(r"\d[\d.,\s]*", text)
    if not match or text[: match.start()].rstrip().endswith("-"):
        return None  # pas de nombre, ou montant négatif (« -5 », « -22 % »)
    number = match.group(0).replace(" ", "").rstrip(".,")
    if "," in number and "." in number:
        if number.rfind(",") > number.rfind("."):  # 1.229,00
            number = number.replace(".", "").replace(",", ".")
        else:  # 1,229.00
            number = number.replace(",", "")
    elif "," in number:
        whole, decimals = number.rsplit(",", 1)
        if len(decimals) <= 2:
            number = f"{whole.replace(',', '')}.{decimals}"
        else:
            number = number.replace(",", "")
    elif number.count(".") > 1 or ("." in number and len(number.rsplit(".", 1)[1]) == 3):
        number = number.replace(".", "")  # 1.229 = mille deux cent vingt-neuf
    try:
        amount = Decimal(number)
    except InvalidOperation:
        return None
    if not 0 < amount < 1_000_000:
        return None
    return amount.quantize(Decimal("0.01"))


def _json_ld_products(soup):
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except ValueError:
            continue
        stack = [data]
        while stack:
            item = stack.pop()
            if isinstance(item, list):
                stack.extend(item)
            elif isinstance(item, dict):
                stack.extend(item.get("@graph", []))
                types = item.get("@type")
                if "Product" in (types if isinstance(types, list) else [types]):
                    yield item


def _first_offer(product):
    offers = product.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    return offers if isinstance(offers, dict) else {}


def _first_image(value):
    if isinstance(value, list):
        value = value[0] if value else ""
    if isinstance(value, dict):
        value = value.get("url", "")
    return value if isinstance(value, str) else ""


def _text(value):
    return value.strip() if isinstance(value, str) else ""


def _meta(soup, key, attr="property"):
    tag = soup.find("meta", attrs={attr: key}) or soup.find("meta", attrs={"name": key})
    return tag["content"].strip() if tag and tag.get("content") else ""


def _attr(soup, selector, attribute):
    tag = soup.select_one(selector)
    return tag.get(attribute, "") if tag else ""


def _select_text(soup, selector):
    tag = soup.select_one(selector)
    return tag.get_text(strip=True) if tag else ""
