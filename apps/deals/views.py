from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from apps.catalog.models import Category, Region
from apps.moderation.models import AuditLog

from .forms import CommentForm, DealSubmissionForm
from .models import Deal, Vote


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
            .prefetch_related("translations")
            .order_by("-temperature")[:3],
        },
    )


def deal_detail(request, slug):
    deal = get_object_or_404(
        Deal.objects.for_user(request.user)
        .select_related("merchant", "category", "submitted_by")
        .prefetch_related("translations"),
        slug=slug,
    )
    comments = deal.comments.filter(deleted_at__isnull=True).select_related("author")
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
    form = DealSubmissionForm(request.POST or None, user=request.user)
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
    return render(request, "deals/submit.html", {"form": form})


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
        return JsonResponse({"temperature": temperature})
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
        comment.save()
        messages.success(request, _("Commentaire publié."))
    else:
        messages.error(request, _("Commentaire refusé : %(e)s") % {"e": form.errors.as_text()})
    return redirect(deal.get_absolute_url())


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
