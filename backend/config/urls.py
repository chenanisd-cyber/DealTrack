from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

# Hors i18n_patterns : l'API ne doit pas être préfixée par la langue.
# Un client REST négocie via l'en-tête Accept-Language, pas via l'URL.
urlpatterns = [
    path("api/v1/", include("apps.api.urls", namespace="api")),
    path("i18n/", include("django.conf.urls.i18n")),
]

# Front-office et back-office, préfixés /fr/, /nl/, /de/.
urlpatterns += i18n_patterns(
    path("back-office/", admin.site.urls),
    path("comptes/", include("apps.accounts.urls", namespace="accounts")),
    path("abonnement/", include("apps.payments.urls", namespace="payments")),
    path("aide/", include("apps.moderation.urls", namespace="support")),
    path("", include("apps.deals.urls", namespace="deals")),
    prefix_default_language=True,
)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG or getattr(settings, "SERVE_MEDIA", False):
    # static() ne fait rien hors DEBUG : en mode partage on sert les photos
    # explicitement (django.views.static.serve refuse les chemins « ../ »).
    from django.urls import re_path
    from django.views.static import serve

    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]

handler403 = "apps.deals.views.forbidden"
handler404 = "apps.deals.views.not_found"
handler500 = "apps.deals.views.server_error"
