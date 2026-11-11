"""
Limitation de débit simple, par clé, appuyée sur le cache.

En production le cache est en base de données (voir prod.py) : le compteur est
donc commun à tous les processus du serveur.
"""

from django.core.cache import cache


def client_ip(request):
    """Adresse du visiteur : première entrée de X-Forwarded-For, sinon REMOTE_ADDR."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return (forwarded.split(",")[0].strip() if forwarded else "") or request.META.get(
        "REMOTE_ADDR", ""
    )


def allow(key, limit, window):
    """
    Compte un appel et dit s'il reste sous la limite. La fenêtre (en secondes)
    démarre au premier appel et n'est pas prolongée par les suivants.
    """
    if cache.add(key, 1, window):
        return True
    try:
        return cache.incr(key) <= limit
    except ValueError:  # la clé a expiré entre add() et incr()
        cache.set(key, 1, window)
        return True
