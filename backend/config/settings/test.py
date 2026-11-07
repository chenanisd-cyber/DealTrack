"""Réglages de test : rapides et déterministes."""

from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-only"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

# MD5 : les tests créent beaucoup de comptes, Argon2 les rendrait très lents.
# La politique de mot de passe reste testée séparément par les validateurs.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
PAYMENT_GATEWAY = "sandbox"

LOGGING["loggers"]["django"]["level"] = "CRITICAL"  # noqa: F405
LOGGING["loggers"]["axes"]["level"] = "CRITICAL"  # noqa: F405
LOGGING["loggers"]["dealtrack.audit"]["level"] = "CRITICAL"  # noqa: F405
