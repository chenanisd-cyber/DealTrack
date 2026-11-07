"""
Abstraction de la passerelle de paiement.

Deux implémentations derrière une interface commune :
  - SandboxGateway  : déterministe, hors ligne, pour le développement et les tests.
  - StripeGateway   : appelle l'API réelle, vérifie la signature des webhooks.

Le principe de sécurité est le même dans les deux cas : le serveur ne voit
jamais un numéro de carte. Le navigateur envoie les coordonnées bancaires
directement au prestataire, qui rend un jeton à usage unique ; c'est ce jeton
que notre code reçoit. Cela place l'application dans le périmètre PCI-DSS le
plus léger (SAQ-A) et supprime le risque de fuite de données de carte.
"""

import hashlib
import hmac
import logging
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings

logger = logging.getLogger("dealtrack.payments")


class PaymentError(Exception):
    """Échec métier du paiement. Message destiné à l'utilisateur."""

    def __init__(self, message, *, code="payment_failed"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ChargeResult:
    reference: str
    succeeded: bool
    card_brand: str = ""
    card_last4: str = ""
    failure_code: str = ""


class BaseGateway:
    name = "base"

    def charge(
        self, *, token, amount: Decimal, currency: str, idempotency_key: str, description: str
    ) -> ChargeResult:
        raise NotImplementedError

    def verify_webhook(self, payload: bytes, signature_header: str) -> bool:
        raise NotImplementedError


class SandboxGateway(BaseGateway):
    """
    Rejoue des réponses réalistes sans réseau.

    Les jetons de test suivent la convention du prestataire : un jeton
    contenant « fail » est refusé, ce qui permet de tester le chemin d'échec
    sans dépendre d'un service externe.
    """

    name = "sandbox"

    def charge(self, *, token, amount, currency, idempotency_key, description):
        if not token or not str(token).startswith("tok_"):
            raise PaymentError("Jeton de paiement invalide.", code="invalid_token")
        if amount <= 0:
            raise PaymentError(
                "Le montant doit être strictement positif.", code="invalid_amount"
            )

        reference = f"sbx_{uuid.uuid5(uuid.NAMESPACE_OID, idempotency_key).hex[:20]}"

        if "fail" in str(token):
            logger.warning("Paiement sandbox refusé token=%s ref=%s", token[:12], reference)
            return ChargeResult(
                reference=reference, succeeded=False, failure_code="card_declined"
            )

        logger.info(
            "Paiement sandbox accepté ref=%s montant=%s %s", reference, amount, currency
        )
        return ChargeResult(
            reference=reference, succeeded=True, card_brand="visa", card_last4="4242"
        )

    def verify_webhook(self, payload, signature_header):
        secret = (settings.STRIPE_WEBHOOK_SECRET or "sandbox-secret").encode()
        expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_header or "")


class StripeGateway(BaseGateway):
    """
    Adaptateur Stripe.

    La clé secrète ne quitte jamais l'environnement. La clé d'idempotence
    empêche un double débit si le client renvoie le formulaire ou si le réseau
    coupe entre l'appel et la réponse.
    """

    name = "stripe"

    def __init__(self):
        if not settings.STRIPE_SECRET_KEY:
            raise PaymentError(
                "STRIPE_SECRET_KEY absent de l'environnement.", code="gateway_misconfigured"
            )
        try:
            import stripe
        except ImportError as exc:
            raise PaymentError(
                "Le paquet stripe n'est pas installé.", code="gateway_unavailable"
            ) from exc
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.api_version = "2024-06-20"
        self._stripe = stripe

    def charge(self, *, token, amount, currency, idempotency_key, description):
        try:
            intent = self._stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Stripe raisonne en centimes
                currency=currency.lower(),
                payment_method=token,
                confirm=True,
                description=description,
                automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
                idempotency_key=idempotency_key,
            )
        except self._stripe.error.CardError as exc:
            logger.warning("Carte refusée : %s", exc.code)
            return ChargeResult(
                reference=getattr(exc, "payment_intent", {}).get("id", "unknown"),
                succeeded=False,
                failure_code=exc.code or "card_declined",
            )
        except self._stripe.error.StripeError as exc:
            # On ne propage pas le message brut du prestataire à l'utilisateur.
            logger.error("Erreur Stripe : %s", exc, exc_info=True)
            raise PaymentError(
                "Le prestataire de paiement est indisponible. Réessayez dans un instant.",
                code="gateway_error",
            ) from exc

        card = (intent.get("charges", {}).get("data") or [{}])[0].get(
            "payment_method_details", {}
        )
        details = card.get("card", {}) if card else {}
        return ChargeResult(
            reference=intent["id"],
            succeeded=intent["status"] == "succeeded",
            card_brand=details.get("brand", ""),
            card_last4=details.get("last4", ""),
        )

    def verify_webhook(self, payload, signature_header):
        """
        Sans cette vérification, n'importe qui peut poster « paiement réussi »
        sur l'URL de webhook et s'offrir un abonnement.
        """
        secret = settings.STRIPE_WEBHOOK_SECRET
        if not secret or not signature_header:
            return False
        try:
            parts = dict(p.split("=", 1) for p in signature_header.split(","))
            timestamp, received = parts["t"], parts["v1"]
        except (ValueError, KeyError):
            return False

        # Fenêtre de cinq minutes : bloque le rejeu d'un webhook capturé.
        if abs(time.time() - int(timestamp)) > 300:
            logger.warning("Webhook hors fenêtre temporelle, rejeté.")
            return False

        signed = f"{timestamp}.".encode() + payload
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, received)


def get_gateway() -> BaseGateway:
    """Fabrique pilotée par le réglage PAYMENT_GATEWAY."""
    name = getattr(settings, "PAYMENT_GATEWAY", "sandbox")
    if name == "stripe":
        return StripeGateway()
    if name == "sandbox":
        return SandboxGateway()
    raise PaymentError(f"Passerelle inconnue : {name}", code="gateway_unknown")
