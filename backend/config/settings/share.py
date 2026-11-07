"""
Partage temporaire du site via un tunnel Cloudflare (lien https://….trycloudflare.com).

Lancement : voir partager.ps1 à la racine du dépôt. Le site tourne sur le PC
du développeur ; le tunnel le rend joignable depuis Internet le temps de la
démonstration (WhatsApp, avis d'amis). Ce n'est PAS un hébergement de
production, mais on y applique déjà les réglages qui comptent dès qu'un
inconnu peut ouvrir le lien :

- DEBUG désactivé : une erreur n'affiche jamais de trace technique ;
- cookies de session et CSRF uniquement en HTTPS (le tunnel est en HTTPS) ;
- back-office fermé aux visiteurs venant d'Internet (mots de passe de
  démonstration publics dans le README) : il reste accessible en local.
"""

from .dev import *  # noqa: F401,F403
from .dev import MIDDLEWARE

DEBUG = False
ALLOWED_HOSTS = [".trycloudflare.com", "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = ["https://*.trycloudflare.com"]

# Le tunnel termine le HTTPS et transmet la requête en HTTP local : cet
# en-tête indique à Django que le visiteur, lui, est bien en HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Photos envoyées par les membres : servies par Django le temps du partage.
SERVE_MEDIA = True

MIDDLEWARE = [*MIDDLEWARE, "config.share_middleware.PublicBackOfficeBlockMiddleware"]
