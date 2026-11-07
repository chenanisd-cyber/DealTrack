import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .gateways import PaymentError, SandboxGateway, get_gateway
from .models import Payment, Plan
from .services import confirm_checkout, start_checkout

logger = logging.getLogger("dealtrack.payments")


@login_required
@require_http_methods(["GET", "POST"])
def subscribe(request, code):
    """
    Souscription Club, en deux temps : le bouton « Payer » crée une session
    chez le prestataire et redirige vers SA page de paiement sécurisée.
    Aucun champ de carte n'existe sur DealTrack.
    """
    plan = get_object_or_404(Plan, code=code, is_active=True)

    if request.method == "POST":
        # Droit de rétractation (art. VI.53 CDE) : pour un service numérique
        # exécuté tout de suite, le consommateur doit le demander expressément.
        if request.POST.get("immediate_start") != "on":
            messages.error(
                request,
                _("Cochez la case pour confirmer le démarrage immédiat de l'abonnement."),
            )
            return render(request, "payments/subscribe.html", {"plan": plan})
        try:
            _payment, checkout_url = start_checkout(
                user=request.user,
                plan=plan,
                success_url=request.build_absolute_uri(reverse("payments:checkout_return")),
                cancel_url=request.build_absolute_uri(reverse("payments:checkout_cancel")),
                request=request,
            )
        except PaymentError as exc:
            messages.error(request, str(exc))
            return render(request, "payments/subscribe.html", {"plan": plan})
        return redirect(checkout_url)

    return render(request, "payments/subscribe.html", {"plan": plan})


def _own_payment(request):
    """Le paiement de la session, uniquement s'il appartient au membre connecté."""
    session_id = request.GET.get("session_id", "")[:120]
    return get_object_or_404(Payment, gateway_reference=session_id, user=request.user)


@login_required
def checkout_return(request):
    payment = _own_payment(request)
    try:
        payment, subscription = confirm_checkout(payment=payment, request=request)
    except PaymentError as exc:
        messages.error(request, str(exc))
        return redirect("payments:plans")
    if subscription is not None:
        messages.success(
            request,
            _("Paiement reçu : abonnement actif jusqu'au %(date)s. Facture %(ref)s.")
            % {"date": subscription.ends_at.strftime("%d/%m/%Y"), "ref": payment.reference},
        )
        return redirect("accounts:profile")
    if payment.status == Payment.Status.FAILED:
        messages.error(request, _("Le paiement a été refusé. Aucun montant n'a été débité."))
    else:
        messages.info(request, _("Paiement en cours de confirmation par le prestataire."))
    return redirect("payments:plans")


@login_required
def checkout_cancel(request):
    payment = _own_payment(request)
    if payment.status == Payment.Status.PENDING:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status"])
    messages.info(request, _("Paiement annulé. Aucun montant n'a été débité."))
    return redirect("payments:plans")


@login_required
@require_http_methods(["GET", "POST"])
def sandbox_checkout(request, session_id):
    """
    Page de paiement SIMULÉE, active uniquement en mode démonstration
    (PAYMENT_GATEWAY=sandbox). Avec de vraies clés Stripe, le membre est
    envoyé sur checkout.stripe.com à la place.
    """
    if get_gateway().name != "sandbox":
        raise Http404
    payment = get_object_or_404(
        Payment, gateway_reference=session_id, user=request.user, status=Payment.Status.PENDING
    )
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "cancel":
            return redirect(f"{reverse('payments:checkout_cancel')}?session_id={session_id}")
        if action not in ("card", "bancontact", "decline"):
            return HttpResponseBadRequest("action inconnue")
        SandboxGateway.record_outcome(session_id, paid=action != "decline", method=action)
        return redirect(f"{reverse('payments:checkout_return')}?session_id={session_id}")
    return render(request, "payments/sandbox_checkout.html", {"payment": payment})


@csrf_exempt  # appelé par Stripe, pas par un navigateur : la signature remplace le CSRF
@require_POST
def stripe_webhook(request):
    """
    Filet de sécurité : si le membre ferme son navigateur avant de revenir sur
    le site, Stripe nous prévient quand même. La signature HMAC est vérifiée,
    sinon n'importe qui pourrait annoncer un « paiement réussi ».
    """
    gateway = get_gateway()
    if not gateway.verify_webhook(request.body, request.headers.get("Stripe-Signature", "")):
        logger.warning("Webhook refusé : signature invalide.")
        return HttpResponse(status=400)
    try:
        event = json.loads(request.body)
    except ValueError:
        return HttpResponse(status=400)
    if event.get("type") == "checkout.session.completed":
        session_id = event.get("data", {}).get("object", {}).get("id", "")
        payment = Payment.objects.filter(gateway_reference=session_id).first()
        if payment:
            confirm_checkout(payment=payment)
    return HttpResponse(status=200)


@login_required
def plans(request):
    return render(
        request, "payments/plans.html", {"plans": Plan.objects.filter(is_active=True)}
    )
