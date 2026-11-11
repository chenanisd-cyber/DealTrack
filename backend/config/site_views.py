"""Pages techniques du site : robots.txt, plan du site, photos envoyées."""

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse
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
