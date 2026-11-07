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
4. la réponse est lue par morceaux et coupée au-delà de MAX_BYTES ;
5. les messages renvoyés au client restent génériques, le détail technique
   part dans les logs.
"""

import ipaddress
import logging
import socket
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ALLOWED_SCHEMES = {"http", "https"}
MAX_BYTES = 1_000_000  # 1 Mo suffit largement pour lire <title> et og:image
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

        response.raise_for_status()
        content = b""
        for chunk in response.iter_content(chunk_size=16_384):
            content += chunk
            if len(content) > MAX_BYTES:
                break
        response.close()
        return url, content[:MAX_BYTES]

    raise UnsafeURLError("trop de redirections")


def fetch_deal_info(url):
    """Renvoie le titre et l'image (Open Graph) de la page, ou une erreur."""
    try:
        final_url, content = _download(url)
    except UnsafeURLError as exc:
        logger.warning("Lien refusé (%s) : %s", exc, url)
        return {"success": False, "error": "unsafe_url"}
    except requests.RequestException as exc:
        logger.info("Lien injoignable (%s) : %s", exc.__class__.__name__, url)
        return {"success": False, "error": "unreachable"}

    soup = BeautifulSoup(content, "html.parser")

    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    elif soup.title:
        title = soup.title.get_text(strip=True).split("|")[0].strip()

    image_url = ""
    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        candidate = urljoin(final_url, og_image["content"].strip())
        # https uniquement : écarte data:, javascript: et le contenu mixte http.
        if urlparse(candidate).scheme == "https":
            image_url = candidate

    return {
        "success": True,
        "title": title[:140],  # max_length du champ Deal.title
        "url": url,
        "image_url": image_url[:800],
    }
