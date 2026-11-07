from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from .gateways import PaymentError
from .models import Plan
from .services import purchase_subscription


@login_required
@require_http_methods(["GET", "POST"])
def subscribe(request, code):
    """
    Souscription Club.

    Le POST attend un jeton `payment_token` produit par le SDK du prestataire
    dans le navigateur. Aucun champ de carte n'existe dans ce formulaire, donc
    aucune donnée bancaire n'atteint ce serveur.
    """
    plan = get_object_or_404(Plan, code=code, is_active=True)

    if request.method == "POST":
        token = (request.POST.get("payment_token") or "").strip()
        try:
            payment, subscription = purchase_subscription(
                user=request.user, plan=plan, token=token, request=request
            )
        except PaymentError as exc:
            messages.error(request, str(exc))
            return render(request, "payments/subscribe.html", {"plan": plan})

        if subscription is None:
            messages.error(
                request, _("Le paiement a été refusé. Aucun montant n'a été débité.")
            )
            return render(request, "payments/subscribe.html", {"plan": plan})

        messages.success(
            request,
            _("Abonnement actif jusqu'au %(date)s. Facture %(ref)s.")
            % {"date": subscription.ends_at.strftime("%d/%m/%Y"), "ref": payment.reference},
        )
        return redirect("accounts:profile")

    return render(request, "payments/subscribe.html", {"plan": plan})


@login_required
def plans(request):
    return render(
        request, "payments/plans.html", {"plans": Plan.objects.filter(is_active=True)}
    )
