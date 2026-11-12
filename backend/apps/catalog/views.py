"""
Espace commerçant : un membre demande à gérer la fiche de son commerce ;
une fois la demande acceptée par la modération, il suit ses offres et tient
sa fiche à jour. Ses offres passent par la modération comme toutes les autres.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from apps.deals.models import Deal, DealStatus
from apps.moderation.models import AuditLog

from .forms import MerchantClaimForm, MerchantProfileForm
from .models import Merchant, MerchantAccount

MAX_PENDING_CLAIMS = 3


def _dashboard(merchant):
    """Chiffres et offres d'un commerce, pour son commerçant."""
    deals = list(
        Deal.objects.filter(merchant=merchant, deleted_at__isnull=True)
        .select_related("merchant")
        .prefetch_related("translations")
        .annotate(
            comment_total=Count(
                "comments", filter=Q(comments__deleted_at__isnull=True), distinct=True
            ),
            favorite_total=Count("favorited_by", distinct=True),
        )
        .order_by("-created_at")[:50]
    )
    live = [d for d in deals if d.status == DealStatus.PUBLISHED]
    return {
        "merchant": merchant,
        "deals": deals,
        "stats": {
            "live": len(live),
            "pending": sum(d.status == DealStatus.PENDING for d in deals),
            "temperature": sum(d.temperature for d in live),
            "comments": sum(d.comment_total for d in live),
            "favorites": sum(d.favorite_total for d in live),
        },
    }


@login_required
@require_http_methods(["GET", "POST"])
def space(request):
    accounts = list(
        MerchantAccount.objects.filter(user=request.user).select_related("merchant")
    )
    approved = [a for a in accounts if a.status == MerchantAccount.Status.APPROVED]
    pending = [a for a in accounts if a.status == MerchantAccount.Status.PENDING]

    # « Vous êtes ce commerçant ? » depuis l'annuaire : le commerce est présélectionné.
    initial = {}
    wanted = Merchant.objects.filter(slug=request.GET.get("commerce", "")).first()
    if wanted:
        initial["merchant"] = wanted
    form = MerchantClaimForm(request.POST or None, user=request.user, initial=initial)

    if request.method == "POST":
        if len(pending) >= MAX_PENDING_CLAIMS:
            messages.error(request, _("Vous avez déjà trois demandes en attente."))
        elif form.is_valid():
            claim = form.save(commit=False)
            claim.user = request.user  # jamais lu dans la requête
            claim.status = MerchantAccount.Status.PENDING
            claim.save()
            AuditLog.record(
                action=AuditLog.Action.MERCHANT_CLAIMED,
                actor=request.user,
                target=claim.merchant,
                request=request,
            )
            messages.success(
                request,
                _("Demande envoyée. Un modérateur la vérifie avant d'ouvrir votre espace."),
            )
            return redirect("merchant:space")

    return render(
        request,
        "merchant/space.html",
        {
            "dashboards": [_dashboard(a.merchant) for a in approved],
            "requests": [a for a in accounts if a.status != MerchantAccount.Status.APPROVED],
            "form": form,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def edit(request, merchant_id):
    """
    Modification de la fiche. Sans compte commerçant accepté pour CE commerce,
    la réponse est 404 : on ne confirme pas l'existence d'une fiche à qui n'y
    a pas droit.
    """
    account = (
        MerchantAccount.objects.filter(
            user=request.user, merchant_id=merchant_id, status=MerchantAccount.Status.APPROVED
        )
        .select_related("merchant")
        .first()
    )
    if account is None:
        raise Http404
    merchant = account.merchant
    form = MerchantProfileForm(request.POST or None, request.FILES or None, instance=merchant)
    if request.method == "POST" and form.is_valid():
        changed = form.changed_data
        form.save()
        if changed:
            AuditLog.record(
                action=AuditLog.Action.MERCHANT_UPDATED,
                actor=request.user,
                target=merchant,
                request=request,
                metadata={"fields": changed},
            )
        messages.success(request, _("La fiche de votre commerce a été mise à jour."))
        return redirect("merchant:space")
    return render(request, "merchant/edit.html", {"form": form, "merchant": merchant})
