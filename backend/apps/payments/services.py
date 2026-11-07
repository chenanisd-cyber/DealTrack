"""
Orchestration du paiement : une seule fonction, transactionnelle.

La règle est que la ligne Payment existe AVANT l'appel au prestataire. Si le
processus meurt entre l'appel et l'enregistrement, on garde une trace en
statut « pending » réconciliable par webhook, plutôt qu'un débit sans trace.
"""

import logging
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.moderation.models import AuditLog

from .gateways import PaymentError, get_gateway
from .models import Payment, Plan, Subscription

logger = logging.getLogger("dealtrack.payments")


def _vat_part(amount_incl: Decimal, rate: Decimal) -> Decimal:
    """Extrait la TVA d'un montant TVAC : montant × taux / (100 + taux)."""
    return (amount_incl * rate / (Decimal("100") + rate)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


@transaction.atomic
def purchase_subscription(*, user, plan: Plan, token: str, request=None):
    """
    Souscrit une formule. Renvoie (payment, subscription|None).

    Idempotence : la clé est dérivée de (utilisateur, formule, jeton). Un double
    envoi du formulaire produit la même clé, donc un seul débit chez le
    prestataire, et l'unicité de gateway_reference verrouille le doublon en base.
    """
    payment = _create_pending_payment(user=user, plan=plan, request=request)

    gateway = get_gateway()
    idempotency_key = f"{user.pk}:{plan.code}:{token}"
    result = gateway.charge(
        token=token,
        amount=payment.amount,
        currency="EUR",
        idempotency_key=idempotency_key,
        description=f"DealTrack {plan.code} — {payment.reference}",
    )

    payment.gateway_reference = result.reference
    return _settle(
        payment,
        succeeded=result.succeeded,
        card_brand=result.card_brand,
        card_last4=result.card_last4,
        failure_code=result.failure_code,
        request=request,
    )


def _create_pending_payment(*, user, plan, request=None):
    if not plan.is_active:
        raise PaymentError("Cette formule n'est plus proposée.", code="plan_inactive")
    if user.is_deleted:
        raise PaymentError("Ce compte est désinscrit.", code="account_closed")
    amount = plan.price
    payment = Payment.objects.create(
        reference=Payment.next_reference(),
        user=user,
        plan=plan,
        amount=amount,
        vat_amount=_vat_part(amount, plan.vat_rate),
        currency="EUR",
        status=Payment.Status.PENDING,
        gateway=get_gateway().name,
        gateway_reference=f"pending-{timezone.now().timestamp()}-{user.pk}",
    )
    AuditLog.record(
        action=AuditLog.Action.PAYMENT_INITIATED,
        actor=user,
        target=payment,
        request=request,
        metadata={"plan": plan.code, "amount": str(amount)},
    )
    return payment


@transaction.atomic
def start_checkout(*, user, plan: Plan, success_url: str, cancel_url: str, request=None):
    """
    Étape 1 du paiement hébergé : crée la ligne Payment « en attente », puis
    la session chez le prestataire. Renvoie (payment, adresse de la page de
    paiement vers laquelle rediriger le navigateur).
    """
    payment = _create_pending_payment(user=user, plan=plan, request=request)
    session = get_gateway().create_checkout(
        payment=payment,
        description=f"DealTrack {plan.label_current} — {payment.reference}",
        success_url=success_url,
        cancel_url=cancel_url,
    )
    payment.gateway_reference = session.id
    payment.save(update_fields=["gateway_reference"])
    return payment, session.url


@transaction.atomic
def confirm_checkout(*, payment, request=None):
    """
    Étape 2 : au retour du membre (ou à l'arrivée du webhook), on DEMANDE au
    prestataire si la session est payée. On ne croit jamais un paramètre
    d'URL du type « ?paid=1 ». Idempotent : un deuxième appel ne crée pas de
    second abonnement.
    """
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status == Payment.Status.SUCCEEDED:
        return payment, getattr(payment, "subscription", None)
    status = get_gateway().checkout_status(payment.gateway_reference)
    if not status.paid and not status.failure_code:
        return payment, None  # pas encore payé : on laisse « en attente »
    return _settle(
        payment,
        succeeded=status.paid,
        card_brand=status.card_brand,
        card_last4=status.card_last4,
        failure_code=status.failure_code,
        request=request,
    )


def _settle(payment, *, succeeded, card_brand, card_last4, failure_code, request=None):
    """Enregistre l'issue du paiement et, s'il a réussi, crée l'abonnement."""
    user, plan = payment.user, payment.plan
    payment.card_brand = card_brand[:20]
    payment.card_last4 = card_last4[:4]

    if not succeeded:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "gateway_reference", "card_brand", "card_last4"])
        AuditLog.record(
            action=AuditLog.Action.PAYMENT_FAILED,
            actor=user,
            target=payment,
            request=request,
            metadata={"failure_code": failure_code},
        )
        return payment, None

    payment.status = Payment.Status.SUCCEEDED
    payment.settled_at = timezone.now()
    payment.save(
        update_fields=["status", "settled_at", "gateway_reference", "card_brand", "card_last4"]
    )

    subscription = Subscription.objects.create(
        user=user,
        plan=plan,
        payment=payment,
        started_at=timezone.now(),
        ends_at=timezone.now() + timedelta(days=plan.duration_days),
    )
    AuditLog.record(
        action=AuditLog.Action.PAYMENT_SUCCEEDED,
        actor=user,
        target=payment,
        request=request,
        metadata={"reference": payment.reference, "subscription": str(subscription.pk)},
    )
    logger.info("Abonnement %s créé pour %s", subscription.pk, user.pk)
    return payment, subscription
