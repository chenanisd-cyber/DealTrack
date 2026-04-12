"""Développement local : DEBUG actif, sécurité transport relâchée."""

from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]
SECRET_KEY = "dev-only-not-for-production"

# En clair sur http://localhost, donc pas de contrainte HTTPS.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

INTERNAL_IPS = ["127.0.0.1"]
