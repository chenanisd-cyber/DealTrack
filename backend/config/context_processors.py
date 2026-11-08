"""
Version des fichiers CSS et JS, ajoutée à leur adresse (?v=…).

Sans elle, un navigateur qui a déjà ouvert le site garde l'ancienne feuille de
style en cache : une nouvelle page s'afficherait alors sans ses styles. La
version est l'empreinte du contenu, elle change donc à chaque modification.
"""

import hashlib
from functools import lru_cache

from django.conf import settings


@lru_cache(maxsize=1)
def _asset_version():
    digest = hashlib.sha256()
    for folder in settings.STATICFILES_DIRS:
        for path in sorted(folder.glob("**/*")):
            if path.suffix in {".css", ".js"} and path.is_file():
                digest.update(path.read_bytes())
    return digest.hexdigest()[:10]


def assets(request):
    return {"ASSET_VERSION": _asset_version()}
