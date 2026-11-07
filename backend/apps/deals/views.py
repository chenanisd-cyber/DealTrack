import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import get_language
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from apps.catalog.merchants import domain_of, find_merchant, name_from_domain
from apps.catalog.models import Category, Merchant, Region
from apps.moderation.models import AuditLog

from .forms import CommentForm, DealSubmissionForm
from .models import Deal, Vote
from .scraper import fetch_deal_info


def deal_list(request):
    """
    Flux public. `for_user` applique le filtre d'accès ; aucun paramètre
    d'URL ne permet d'élargir le périmètre.
    """
    # « translations » est préchargé : les propriétés title_current et
    # description_current lisent le cache, sinon chaque carte du flux
    # déclencherait sa propre requête.
    deals = (
        Deal.objects.for_user(request.user)
        .select_related("merchant", "category", "submitted_by")
        .prefetch_related("regions", "translations")
        .annotate(comment_total=Count("comments", filter=Q(comments__deleted_at__isnull=True)))
    )

    # Les filtres viennent de l'URL : on valide contre le référentiel plutôt
    # que d'injecter la valeur telle quelle dans le queryset.
    region_code = request.GET.get("region", "")
    if region_code and Region.objects.filter(code=region_code).exists():
        deals = deals.filter(regions__code=region_code)

    category_slug = request.GET.get("categorie", "")
    if category_slug and Category.objects.filter(slug=category_slug).exists():
        deals = deals.filter(category__slug=category_slug)

    if request.GET.get("local") == "1":
        deals = deals.filter(merchant__is_local_independent=True)

    sort = request.GET.get("tri", "hot")
    deals = deals.order_by({"new": "-published_at", "price": "price"}.get(sort, "-temperature"))

    page = Paginator(deals, 10).get_page(request.GET.get("page"))
    return render(
        request,
        "deals/list.html",
        {
            "page_obj": page,
            "regions": Region.objects.all(),
            "categories": Category.objects.filter(is_active=True),
            "current_region": region_code,
            "current_sort": sort,
            "hot_deals": Deal.objects.live()
            .select_related("merchant")
            .prefetch_related("translations")
            .order_by("-temperature")[:3],
        },
    )


def deal_detail(request, slug):
    deal = get_object_or_404(
        Deal.objects.for_user(request.user)
        .select_related("merchant", "category", "submitted_by")
        .prefetch_related("translations", "gallery"),
        slug=slug,
    )
    comments = (
        deal.comments.filter(deleted_at__isnull=True)
        .select_related("author")
        .prefetch_related("translations")
    )
    user_vote = None
    if request.user.is_authenticated:
        user_vote = Vote.objects.filter(deal=deal, user=request.user).first()

    return render(
        request,
        "deals/detail.html",
        {
            "deal": deal,
            "comments": comments,
            "comment_form": CommentForm(),
            "user_vote": user_vote.value if user_vote else 0,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def deal_submit(request):
    # « Proposer un deal ici » depuis l'annuaire : le marchand est présélectionné.
    initial = {}
    merchant_id = request.GET.get("marchand", "")
    if merchant_id and Merchant.objects.filter(pk=_safe_uuid(merchant_id)).exists():
        initial["merchant"] = merchant_id
    form = DealSubmissionForm(
        request.POST or None, request.FILES or None, user=request.user, initial=initial
    )
    if request.method == "POST" and form.is_valid():
        deal = form.save()
        AuditLog.record(
            action=AuditLog.Action.DEAL_SUBMITTED,
            actor=request.user,
            target=deal,
            request=request,
        )
        messages.success(
            request,
            _(
                "Merci. Votre offre part en modération et sera visible sous "
                "deux heures environ."
            ),
        )
        return redirect("accounts:profile")
    return render(
        request, "deals/submit.html", {"form": form, "wizard_messages": _wizard_messages()}
    )


def _wizard_messages():
    """Textes de l'assistant de publication, traduits ici et lus par submit.js."""
    return {
        "invalid": _("Veuillez entrer un lien valide (http:// ou https://)."),
        "refused": _("Ce lien a été refusé. Seules les pages web publiques sont acceptées."),
        "tooMany": _("Trop de vérifications en peu de temps. Réessayez dans une minute."),
        "blocked": _(
            "Ce site bloque la lecture automatique : complétez les champs vous-même, "
            "le lien est déjà renseigné."
        ),
        "failed": _("Impossible de lire cette page : complétez le formulaire vous-même."),
        "found": _("Récupéré automatiquement :"),
        "missing": _("À compléter :"),
        "check": _("Vérifiez avant d’envoyer."),
        "fields": {
            "title": _("titre"),
            "price": _("prix"),
            "reference": _("prix de référence (30 jours)"),
            "photo": _("photo"),
            "merchant": _("marchand"),
            "description": _("description"),
        },
        "merchantUnknown": _("Marchand à préciser à l'étape « Derniers détails »"),
        "main": _("Image principale"),
        "makeMain": _("Choisir comme image principale"),
        "remove": _("Retirer l'image"),
        "maxImages": _("Huit images au maximum."),
        "httpsOnly": _("L'adresse de l'image doit être en HTTPS."),
        "online": _("En ligne"),
        "inStore": _("En magasin"),
        "promo": _("Code :"),
        "availableAt": _("Dispo. chez"),
    }


@login_required
@require_POST
def deal_vote(request, slug):
    """
    Vote. require_POST plus le jeton CSRF : un GET ne modifie jamais l'état,
    donc aucune page tierce ne peut faire voter un membre à son insu.
    """
    deal = get_object_or_404(Deal.objects.live(), slug=slug)
    try:
        value = int(request.POST.get("value", 0))
    except (TypeError, ValueError):
        return HttpResponseBadRequest("valeur invalide")
    if value not in (-1, 1):
        return HttpResponseBadRequest("valeur invalide")

    temperature = Vote.cast(deal=deal, user=request.user, value=value)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        # Vote en direct (dealtrack.js) : la page met à jour la température
        # et l'état des boutons sans se recharger.
        vote = Vote.objects.filter(deal=deal, user=request.user).first()
        return JsonResponse(
            {"temperature": temperature, "user_vote": vote.value if vote else 0}
        )
    return redirect(deal.get_absolute_url())


@login_required
@require_POST
def comment_create(request, slug):
    deal = get_object_or_404(Deal.objects.for_user(request.user), slug=slug)
    form = CommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.deal = deal
        comment.author = request.user
        # Langue de la page depuis laquelle le membre écrit (fr, nl ou de).
        comment.language = get_language() or "fr"
        comment.save()
        messages.success(request, _("Commentaire publié."))
    else:
        messages.error(request, _("Commentaire refusé : %(e)s") % {"e": form.errors.as_text()})
    return redirect(deal.get_absolute_url())


def local_merchants(request):
    """
    Annuaire des commerçants indépendants (données OpenStreetMap), filtrable
    par ville. La ville vient de l'URL : elle n'est utilisée que si elle existe
    dans la base, jamais injectée telle quelle.
    """
    merchants = Merchant.objects.filter(is_local_independent=True).order_by("city", "name")
    # sorted(set()) et non .distinct() : le tri par nom ajouté par order_by
    # ferait ressortir une ville par commerçant.
    cities = sorted(set(merchants.exclude(city="").values_list("city", flat=True)))
    current_city = request.GET.get("ville", "")
    if current_city in cities:
        merchants = merchants.filter(city=current_city)
    else:
        current_city = ""
    local_deals = (
        Deal.objects.live()
        .filter(merchant__is_local_independent=True)
        .select_related("merchant")
        .prefetch_related("translations")[:10]
    )
    return render(
        request,
        "deals/local_merchants.html",
        {
            "merchants": merchants,
            "cities": cities,
            "current_city": current_city,
            "local_deals": local_deals,
        },
    )


def _safe_uuid(value):
    import uuid

    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


# --------------------------------------------------------------------------
# Pages d'erreur — pas de trace technique renvoyée au visiteur
# --------------------------------------------------------------------------
def forbidden(request, exception=None):
    AuditLog.record(
        action=AuditLog.Action.PERMISSION_DENIED, actor=request.user, request=request
    )
    return render(request, "errors/403.html", status=403)


def not_found(request, exception=None):
    return render(request, "errors/404.html", status=404)


def server_error(request):
    return render(request, "errors/500.html", status=500)


# --------------------------------------------------------------------------
# Pré-remplissage du formulaire de dépôt (appel AJAX depuis submit.html)
# --------------------------------------------------------------------------
SCRAPE_LIMIT = 10  # appels autorisés…
SCRAPE_WINDOW = 60  # …par fenêtre de 60 secondes et par utilisateur


@login_required
@require_POST
def scrape_link_view(request):
    """
    Réservé aux membres connectés (seuls eux peuvent publier) et protégé par
    le jeton CSRF envoyé en en-tête X-CSRFToken. Le nombre d'appels est
    limité : sans cela, le serveur servirait de robot de téléchargement.
    La validation de l'URL elle-même (anti-SSRF) est faite dans scraper.py.
    """
    key = f"scrape-rate:{request.user.pk}"
    calls = cache.get_or_set(key, 0, SCRAPE_WINDOW)
    if calls >= SCRAPE_LIMIT:
        return JsonResponse({"success": False, "error": "rate_limited"}, status=429)
    cache.incr(key)

    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"success": False, "error": "bad_request"}, status=400)

    url = data.get("url") if isinstance(data, dict) else None
    if not isinstance(url, str) or not url.strip() or len(url) > 800:
        return JsonResponse({"success": False, "error": "bad_request"}, status=400)

    info = fetch_deal_info(url.strip())
    if info.get("success"):
        page_url = info.get("final_url") or url
        merchant = match_merchant(page_url)
        if merchant:
            info["merchant_id"] = str(merchant.pk)
            info["merchant_name"] = merchant.name
            info["is_cross_border"] = merchant.country != "BE"
        else:
            # Marchand inconnu : nom proposé, créé à la publication (non vérifié).
            info["merchant_name"] = info.get("site_name") or name_from_domain(
                domain_of(page_url)
            )
            info["merchant_is_new"] = True
    return JsonResponse(info)


# Reconnaissance du marchand par domaine : voir apps/catalog/merchants.py.
match_merchant = find_merchant
