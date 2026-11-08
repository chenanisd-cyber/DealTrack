"""
Production. Tout ce qui est sensible vient de l'environnement et le démarrage
échoue si une variable indispensable manque, plutôt que de tourner en
configuration dégradée.

Hébergement visé : Render (voir render.yaml à la racine du dépôt). Render
fournit la base dans DATABASE_URL et le nom public du site dans
RENDER_EXTERNAL_HOSTNAME ; les deux sont pris en compte ici. Les variables
POSTGRES_* restent possibles pour un autre hébergeur.
"""

from urllib.parse import parse_qs, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE, env

DEBUG = False
SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)


# -- Hôtes autorisés ----------------------------------------------------------
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in env("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
_render_host = env("RENDER_EXTERNAL_HOSTNAME", "")
if _render_host:
    ALLOWED_HOSTS.append(_render_host)
    CSRF_TRUSTED_ORIGINS.append(f"https://{_render_host}")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS ou RENDER_EXTERNAL_HOSTNAME requis.")


# -- Base de données -----------------------------------------------------------
def database_from_url(url):
    """postgres://user:mdp@hôte:port/base?sslmode=… (sqlite:///chemin : essai local)."""
    parts = urlsplit(url)
    if parts.scheme == "sqlite":
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": parts.path.lstrip("/")}
    if parts.scheme not in ("postgres", "postgresql"):
        raise ImproperlyConfigured(f"DATABASE_URL : moteur inconnu ({parts.scheme}).")
    query = parse_qs(parts.query)
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parts.path.lstrip("/")),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname or "",
        "PORT": str(parts.port or 5432),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"sslmode": query.get("sslmode", [env("POSTGRES_SSLMODE", "prefer")])[0]},
    }


if env("DATABASE_URL", ""):
    DATABASES = {"default": database_from_url(env("DATABASE_URL"))}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("POSTGRES_DB", required=True),
            "USER": env("POSTGRES_USER", required=True),
            "PASSWORD": env("POSTGRES_PASSWORD", required=True),
            "HOST": env("POSTGRES_HOST", "localhost"),
            "PORT": env("POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 60,
            "OPTIONS": {"sslmode": env("POSTGRES_SSLMODE", "require")},
        }
    }


# -- Transport -----------------------------------------------------------------
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True


# -- Fichiers statiques et photos ------------------------------------------------
# WhiteNoise sert le CSS et le JS directement depuis Django (compressés, noms
# avec empreinte, cache long) : pas besoin d'un serveur web séparé.
MIDDLEWARE = [
    MIDDLEWARE[0],  # SecurityMiddleware d'abord
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
# Photos envoyées par les membres. Sur l'offre gratuite de Render, le disque
# est effacé à chaque déploiement : ces photos-là disparaissent alors (les
# photos des marchands, affichées par lien, ne sont pas concernées).
SERVE_MEDIA = env("SERVE_MEDIA", "1") == "1"


# -- Courrier --------------------------------------------------------------------
if env("EMAIL_HOST", ""):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = env("EMAIL_HOST")
    EMAIL_PORT = int(env("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
else:
    # Sans serveur d'envoi configuré, les e-mails (alertes) sont écrits dans
    # le journal de l'hébergeur au lieu de faire échouer le site.
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

SITE_URL = env("SITE_URL", f"https://{_render_host}" if _render_host else "")

# Paiement réel : une clé Stripe « live » est acceptée uniquement ici.
STRIPE_ALLOW_LIVE = True
