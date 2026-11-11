"""
En-têtes de sécurité que Django ne pose pas lui-même.

Content-Security-Policy : la liste de ce que le navigateur a le droit de
charger et d'exécuter sur nos pages. C'est la seconde ligne de défense contre
le XSS : même si un texte piégé passait l'échappement des gabarits, son
script ne s'exécuterait pas, car seuls les fichiers .js du site sont admis.

Choix, directive par directive :
- script-src 'self'       aucun script en ligne ni tiers ; les gabarits n'ont
                          ni <script> en ligne ni attribut onclick/onerror ;
- style-src 'self'        une seule feuille de style, servie par le site ;
- style-src-attr          les attributs style="…" restent permis : ils ne
                          peuvent pas exécuter de code ;
- img-src https:          les photos des offres viennent des sites marchands ;
                          blob: sert à l'aperçu d'une photo avant envoi ;
- form-action             nos formulaires, plus la page de paiement Stripe vers
                          laquelle la souscription redirige ;
- frame-ancestors 'none'  le site ne s'affiche dans aucun cadre (clickjacking).
"""

from django.conf import settings

CSP_DIRECTIVES = (
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "style-src-attr 'unsafe-inline'",
    "img-src 'self' https: data: blob:",
    "font-src 'self'",
    "connect-src 'self'",
    "form-action 'self' https://checkout.stripe.com",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "object-src 'none'",
)

# Fonctions du navigateur dont le site n'a pas besoin : désactivées, y compris
# pour un éventuel contenu tiers.
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


def build_csp():
    directives = list(CSP_DIRECTIVES)
    if getattr(settings, "SECURE_SSL_REDIRECT", False):
        # En production (HTTPS partout) : une image en http:// est demandée en https://.
        directives.append("upgrade-insecure-requests")
    return "; ".join(directives)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.csp = build_csp()

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        # Les pages d'erreur techniques de Django (DEBUG) ont leurs propres
        # styles et scripts en ligne : elles n'existent qu'en développement.
        if not (settings.DEBUG and response.status_code in (404, 500)):
            response.setdefault("Content-Security-Policy", self.csp)
        return response
