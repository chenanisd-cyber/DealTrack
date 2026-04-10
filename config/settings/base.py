"""
Réglages communs à tous les environnements.

Rien de sensible ici : la clé secrète, les identifiants de base de données et les
clés du prestataire de paiement viennent exclusivement de l'environnement.
Voir .env.example.
"""

import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise ImproperlyConfigured(f"Variable d'environnement manquante : {name}")
    return value


# --------------------------------------------------------------------------
# Cœur
# --------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-only-not-for-production")
DEBUG = env("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [h for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Tiers
    "rest_framework",
    "django_filters",
    "axes",
    # Applications du projet
    "apps.accounts",
    "apps.catalog",
    "apps.deals",
    "apps.payments",
    "apps.moderation.apps.ModerationConfig",
    "apps.api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # LocaleMiddleware doit suivre Session et précéder Common.
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Journalise chaque requête authentifiée modifiant l'état (piste d'audit).
    "apps.moderation.middleware.AuditTrailMiddleware",
    # AxesMiddleware doit venir en dernier : il intercepte les échecs de connexion.
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------------------------------
# Base de données
# --------------------------------------------------------------------------
# SQLite en développement, PostgreSQL en production (voir prod.py).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "OPTIONS": {"transaction_mode": "IMMEDIATE"},
    }
}

# Les clés primaires sont déclarées explicitement modèle par modèle
# (UUID pour les entités métier, BigAutoField pour les tables append-only).
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --------------------------------------------------------------------------
# Authentification et politique de mot de passe
# --------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    # AxesStandaloneBackend doit être premier : il bloque avant toute
    # vérification de mot de passe une fois le compte verrouillé.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Argon2 en tête : résistant au GPU, recommandé par l'OWASP.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    # Validateur maison : classes de caractères + rejet des motifs séquentiels.
    {"NAME": "apps.accounts.validators.ComplexityValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "deals:list"
LOGOUT_REDIRECT_URL = "deals:list"

# --------------------------------------------------------------------------
# Force brute (django-axes)
# --------------------------------------------------------------------------
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=15)
# Verrou sur le couple (IP, identifiant) : bloquer la seule IP punit les
# utilisateurs derrière un NAT partagé, bloquer le seul compte permet à un
# attaquant de verrouiller n'importe qui.
AXES_LOCKOUT_PARAMETERS = [["ip_address", "username"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "registration/lockout.html"
AXES_VERBOSE = True
AXES_ENABLE_ACCESS_FAILURE_LOG = True

# --------------------------------------------------------------------------
# Sessions et CSRF
# --------------------------------------------------------------------------
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

CSRF_COOKIE_HTTPONLY = False  # lu par le JS pour l'en-tête X-CSRFToken
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_USE_SESSIONS = False
CSRF_FAILURE_VIEW = "apps.moderation.views.csrf_failure"

# --------------------------------------------------------------------------
# En-têtes de sécurité
# --------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# --------------------------------------------------------------------------
# Internationalisation — front-office trilingue
# --------------------------------------------------------------------------
LANGUAGE_CODE = "fr"
LANGUAGES = [
    ("fr", _("Français")),
    ("nl", _("Nederlands")),
    ("de", _("Deutsch")),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
USE_I18N = True
USE_TZ = True
TIME_ZONE = "Europe/Brussels"
LANGUAGE_COOKIE_NAME = "dealtrack_language"
LANGUAGE_COOKIE_HTTPONLY = False
LANGUAGE_COOKIE_SAMESITE = "Lax"

# --------------------------------------------------------------------------
# Fichiers statiques
# --------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# --------------------------------------------------------------------------
# API REST
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        # Fermé par défaut. Chaque vue ouvre explicitement ce qu'elle expose.
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/hour",
        "user": "1000/hour",
        "vote": "60/hour",
        "deal-write": "20/hour",
        "token": "10/hour",
    },
    "EXCEPTION_HANDLER": "apps.api.exceptions.api_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env("JWT_SIGNING_KEY", SECRET_KEY),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# --------------------------------------------------------------------------
# Paiement
# --------------------------------------------------------------------------
# "sandbox" rejoue les réponses du prestataire hors ligne ; "stripe" appelle
# l'API réelle. Aucune donnée de carte ne transite jamais par nos serveurs :
# le client obtient un jeton côté prestataire, nous ne voyons que ce jeton.
PAYMENT_GATEWAY = env("PAYMENT_GATEWAY", "sandbox")
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", "")

# --------------------------------------------------------------------------
# Conservation des données (RGPD + obligations comptables belges)
# --------------------------------------------------------------------------
# Le droit à l'effacement cède devant l'obligation légale de conservation des
# pièces comptables. On anonymise, on ne supprime pas.
ACCOUNTING_RETENTION_YEARS = 7
AUDIT_LOG_RETENTION_DAYS = 365
ANONYMISED_EMAIL_DOMAIN = "anonymised.dealtrack.invalid"

# --------------------------------------------------------------------------
# Journalisation
# --------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "app_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "dealtrack.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "security.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 10,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {"handlers": ["console", "app_file"], "level": "INFO"},
        "django.security": {
            "handlers": ["console", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "app_file"],
            "level": "ERROR",
            "propagate": False,
        },
        "axes": {"handlers": ["console", "security_file"], "level": "INFO", "propagate": False},
        "dealtrack.audit": {
            "handlers": ["console", "security_file"],
            "level": "INFO",
            "propagate": False,
        },
        "dealtrack.payments": {
            "handlers": ["console", "app_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

DEFAULT_FROM_EMAIL = "no-reply@dealtrack.be"
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
