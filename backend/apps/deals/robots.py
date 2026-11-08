"""
Respect du fichier robots.txt avant toute lecture automatique d'une page.

Un site indique dans /robots.txt les pages qu'un robot ne doit pas lire.
DealTrack le consulte avant chaque lecture en direct (comparaison VIP) et
s'abstient si la page est interdite. Exemples relevés : MediaMarkt interdit
ses pages de recherche (« Disallow: /*/search.html »), bol.com aussi
(« Disallow: /*/s/ ») ; Amazon.com.be les autorise.

Règles appliquées (RFC 9309) :
- le groupe « DealTrackBot » s'il existe, sinon le groupe « * » ;
- jokers « * » et fin d'adresse « $ » ;
- la règle la plus longue l'emporte, « Allow » en cas d'égalité ;
- pas de robots.txt (404) : tout est permis ;
- robots.txt refusé ou serveur en erreur : rien n'est permis.
Le fichier est gardé 24 h en cache par site.
"""

import logging
import re
from urllib.parse import urlsplit

import requests
from django.core.cache import cache

logger = logging.getLogger(__name__)

AGENT = "dealtrackbot"
CACHE_SECONDS = 60 * 60 * 24
DENY_ALL = [("disallow", "/")]


def parse_rules(text, agent=AGENT):
    """Règles Allow/Disallow du groupe qui s'applique à notre robot."""
    groups, rules, last_was_agent = [], None, False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        field, sep, value = line.partition(":")
        if not sep:
            continue
        field, value = field.strip().lower(), value.strip()
        if field == "user-agent":
            if not last_was_agent:
                agents, rules = [], []
                groups.append((agents, rules))
            agents.append(value.lower())
            last_was_agent = True
        elif field in ("allow", "disallow") and rules is not None:
            rules.append((field, value))
            last_was_agent = False
    own = [r for agents, rs in groups if agent in agents for r in rs]
    if own:
        return own
    return [r for agents, rs in groups if "*" in agents for r in rs]


def is_allowed(rules, path):
    best = None
    for field, pattern in rules:
        if not pattern:
            continue
        regex = "^" + re.escape(pattern).replace(r"\*", ".*").replace(r"\$", "$")
        if re.match(regex, path):
            longer = best is None or len(pattern) > len(best[1])
            tie_allow = best is not None and len(pattern) == len(best[1]) and field == "allow"
            if longer or tie_allow:
                best = (field, pattern)
    return best is None or best[0] == "allow"


def _fetch_rules(scheme, host):
    from .scraper import BlockedError, UnsafeURLError, _download

    try:
        _, content = _download(f"{scheme}://{host}/robots.txt")
    except BlockedError:
        return DENY_ALL
    except requests.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else 500
        return [] if 400 <= status < 500 else DENY_ALL
    except (UnsafeURLError, OSError, requests.RequestException):
        return DENY_ALL
    return parse_rules(content.decode("utf-8", "ignore"))


def robots_allows(url):
    """Vrai si le robots.txt du site autorise DealTrackBot à lire cette adresse."""
    parts = urlsplit(url)
    key = f"robots:{parts.scheme}:{parts.netloc.lower()}"
    rules = cache.get(key)
    if rules is None:
        rules = _fetch_rules(parts.scheme, parts.netloc)
        cache.set(key, rules, CACHE_SECONDS)
    path = (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    allowed = is_allowed(rules, path)
    if not allowed:
        logger.info("robots.txt interdit la lecture de %s", url)
    return allowed
