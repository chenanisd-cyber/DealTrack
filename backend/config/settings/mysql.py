"""
Variante MySQL du développement (utilisée pour produire le DUMP phpMyAdmin).

Django rend le projet indépendant du moteur : les mêmes modèles et migrations
créent les tables sous SQLite (développement), MySQL (ce fichier) ou
PostgreSQL (production). Seule la connexion change.

Les identifiants ne sont JAMAIS dans le code : ils sont lus dans un fichier
d'options MySQL local, hors dépôt Git (voir database/README.md) :

    [client]
    user=dealtrack
    password=…
    host=127.0.0.1
    port=3306
    default-character-set=utf8mb4

Utilisation :
    set MYSQL_OPTION_FILE=C:\\chemin\\vers\\client.cnf
    python manage.py migrate --settings=config.settings.mysql
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .dev import *  # noqa: F401,F403
from .dev import BASE_DIR

OPTION_FILE = os.environ.get(
    "MYSQL_OPTION_FILE", str(Path(BASE_DIR).parent / ".tools" / "mysql" / "client.cnf")
)
if not Path(OPTION_FILE).is_file():
    raise ImproperlyConfigured(f"Fichier d'options MySQL introuvable : {OPTION_FILE}")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("MYSQL_DATABASE", "dealtrack"),
        "OPTIONS": {
            "read_default_file": OPTION_FILE,
            "charset": "utf8mb4",
            # Mode strict : MySQL refuse une valeur tronquée au lieu de la
            # couper silencieusement (même rigueur que les contraintes Django).
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}
