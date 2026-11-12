"""Pages techniques : robots.txt, plan du site, photos envoyées, application installable."""

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.utils.cache import patch_cache_control
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET
from django.views.static import serve

from apps.deals.models import Deal

# Espaces sans intérêt pour un moteur de recherche (comptes, paiement,
# back-office, API) et résultats de recherche, dupliqués à l'infini.
ROBOTS_DISALLOW = (
    "/api/",
    "/i18n/",
    "/*/back-office/",
    "/*/comptes/",
    "/*/commercant/",
    "/*/abonnement/",
    "/*?q=",
)


@require_GET
@cache_control(public=True, max_age=86400)
def robots_txt(request):
    lines = ["User-agent: *", *(f"Disallow: {path}" for path in ROBOTS_DISALLOW), ""]
    lines.append(f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}")
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


class DealSitemap(Sitemap):
    """Les offres publiées, dans les trois langues (balises hreflang)."""

    i18n = True
    alternates = True
    changefreq = "daily"
    limit = 2000

    def items(self):
        return Deal.objects.live().order_by("-published_at")

    def lastmod(self, deal):
        return deal.updated_at


class PageSitemap(Sitemap):
    i18n = True
    alternates = True
    changefreq = "daily"

    def items(self):
        return ["deals:list", "deals:local", "support:contact"]

    def location(self, name):
        return reverse(name)


SITEMAPS = {"deals": DealSitemap, "pages": PageSitemap}


def media(request, path):
    """
    Photos envoyées par les membres. Chaque fichier porte un nom aléatoire
    (UUID) et n'est jamais modifié : le navigateur peut le garder longtemps.
    """
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    patch_cache_control(response, public=True, max_age=60 * 60 * 24 * 30, immutable=True)
    return response


# --------------------------------------------------------------------------
# Application installable (PWA)
# --------------------------------------------------------------------------
# Le site s'installe sur un téléphone comme une application : icône sur
# l'écran d'accueil, affichage plein écran, page d'attente sans connexion.
# Il n'y a rien à publier sur un magasin d'applications, et c'est le même
# code que le site.
@require_GET
@cache_control(public=True, max_age=3600)
def manifest(request):
    """Carte d'identité de l'application, lue par le navigateur à l'installation."""
    data = {
        "name": "DealTrack.be",
        "short_name": "DealTrack",
        "description": "La plateforme communautaire des bons plans en Belgique.",
        "lang": "fr",
        "start_url": "/fr/?source=pwa",
        "scope": "/",
        "display": "standalone",
        "background_color": "#01182B",
        "theme_color": "#01182B",
        "icons": [
            {"src": static("img/icon-192.png"), "sizes": "192x192", "type": "image/png"},
            {"src": static("img/icon-512.png"), "sizes": "512x512", "type": "image/png"},
            {
                "src": static("img/icon-maskable-512.png"),
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable",
            },
        ],
        "shortcuts": [
            {"name": "Publier un deal", "url": "/fr/publier/"},
            {"name": "Mes favoris", "url": "/fr/comptes/favoris/"},
        ],
    }
    return JsonResponse(data, content_type="application/manifest+json")


@require_GET
def service_worker(request):
    """
    Script d'arrière-plan de l'application. Servi à la racine pour couvrir
    tout le site, et jamais mis en cache longtemps : une nouvelle version du
    site doit être prise en compte à la visite suivante.
    """
    from .context_processors import assets

    response = render(
        request,
        "pwa/sw.js",
        {
            "version": assets(request)["ASSET_VERSION"],
            "precache": [
                reverse("offline"),
                static("css/dealtrack.css"),
                static("fonts/jost-latin.woff2"),
                static("img/icon-192.png"),
            ],
        },
        content_type="application/javascript; charset=utf-8",
    )
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
    return response


@require_GET
def offline(request):
    """Page affichée par l'application quand le téléphone n'a pas de connexion."""
    return render(request, "pwa/offline.html")
