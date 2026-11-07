"""Protection propre au mode partage (config/settings/share.py)."""

import re

from django.http import Http404

BACK_OFFICE = re.compile(r"^/(?:fr|nl|de)/back-office/")


class PublicBackOfficeBlockMiddleware:
    """
    Le back-office répond « page introuvable » aux visiteurs venant du tunnel
    public : les identifiants de démonstration sont dans le README, donc
    n'importe qui pourrait sinon s'y connecter. En local (localhost), il reste
    accessible pour le développeur.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":")[0]
        # Le tunnel ajoute toujours l'en-tête Cf-Connecting-Ip (adresse du
        # visiteur) : sa présence suffit à savoir que la requête vient d'Internet,
        # même si l'en-tête Host a été réécrit en « localhost ».
        from_internet = "HTTP_CF_CONNECTING_IP" in request.META or host not in (
            "localhost",
            "127.0.0.1",
        )
        if BACK_OFFICE.match(request.path) and from_internet:
            raise Http404
        return self.get_response(request)
