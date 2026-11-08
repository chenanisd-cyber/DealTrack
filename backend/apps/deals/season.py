"""
Bannière saisonnière de la page d'accueil.

Novembre : « Black November » (le mois du Black Friday).
Décembre : « Black December » (les achats des fêtes).
Le reste de l'année, aucune bannière. Le mois se lit à la date du jour, la
bannière change donc toute seule le 1er décembre.
"""

from django.utils.translation import gettext_lazy as _

SEASONS = {
    11: {
        "key": "black-november",
        "title": "Black November",
        "tagline": _("Le mois des bons plans, c'est maintenant !"),
    },
    12: {
        "key": "black-december",
        "title": "Black December",
        "tagline": _("Les meilleurs prix pour les cadeaux des fêtes."),
    },
}


def season_banner(today):
    season = SEASONS.get(today.month)
    if season is None:
        return None
    return {**season, "year": today.year}
