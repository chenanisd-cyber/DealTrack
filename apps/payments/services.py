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

    gateway = get_gateway()
    idempotency_key = f"{user.pk}:{plan.code}:{token}"
    result = gateway.charge(
        token=token,
        amount=amount,
        currency="EUR",
        idempotency_key=idempotency_key,
        description=f"DealTrack {plan.code} — {payment.reference}",
    )

    payment.gateway_reference = result.reference
    payment.card_brand = result.card_brand
    payment.card_last4 = result.card_last4

    if not result.succeeded:
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "gateway_reference", "card_brand", "card_last4"])
        AuditLog.record(
            action=AuditLog.Action.PAYMENT_FAILED,
            actor=user,
            target=payment,
            request=request,
            metadata={"failure_code": result.failure_code},
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
